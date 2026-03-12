"""
Base Agent for NexusAgent

Provides the foundation for all agents with enhanced tool support and ReAct loop.
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from coordinator.core.blackboard import GlobalState, AgentStatus, AgentMessage
from coordinator.core.tool import BaseTool, ToolExecutionResult


logger = logging.getLogger("BaseAgent")


class BaseAgent(ABC):
    """Base class for all multi-agents with enhanced tool support and ReAct loop.
    
    Enhanced Features:
    1. Tool mounting and management
    2. ReAct (Reasoning + Acting) loop
    3. Automatic tool call parsing from LLM responses
    4. Observation recording to blackboard
    5. Error recovery and retry logic
    
    Workflow:
    1. Initialize: Connect to blackboard and register tools
    2. Subscribe: Subscribe to messages from other agents
    3. Execute: Run ReAct loop
       - Think: Query LLM and analyze
       - Act: Execute tools if needed
       - Observe: Record results to blackboard
       - Repeat: Continue until complete
    4. Communicate: Send results via blackboard
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        blackboard: GlobalState,
        llm_client: Optional[OpenAI] = None,
        llm_model: str = "Pro/zai-org/GLM-5",
        max_iterations: int = 10
    ):
        """Initialize agent.
        
        Args:
            name: Agent name
            system_prompt: System prompt from SKILL.md
            blackboard: Global state blackboard
            llm_client: OpenAI client (optional)
            llm_model: LLM model name
            max_iterations: Maximum iterations for ReAct loop
        """
        self.name = name
        self.system_prompt = system_prompt
        self.blackboard = blackboard
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.max_iterations = max_iterations
        
        self.tools: Dict[str, BaseTool] = {}
        self.status = AgentStatus.NOT_STARTED
        self.observations: List[Dict[str, Any]] = []
        
        logger.info(f"Agent initialized: {name}")
    
    def add_tool(self, tool: BaseTool) -> None:
        """Add tool to agent.
        
        Args:
            tool: Tool instance
        """
        if not isinstance(tool, BaseTool):
            logger.warning(f"[{self.name}] Cannot add non-BaseTool: {type(tool)}")
            return
        
        self.tools[tool.name] = tool
        logger.debug(f"[{self.name}] Added tool: {tool.name}")
    
    def mount_tools(self, tools: List[BaseTool]) -> None:
        """Mount multiple tools to agent.
        
        Args:
            tools: List of tool instances
        """
        for tool in tools:
            self.add_tool(tool)
    
    async def register_tools(self) -> None:
        """Register all tools (can be overridden by subclasses)."""
        pass
    
    async def initialize(self) -> None:
        """Initialize agent.
        
        Updates status to blackboard and registers tools.
        """
        await self.blackboard.update_agent_status(self.name, AgentStatus.NOT_STARTED)
        await self.register_tools()
        self.status = AgentStatus.NOT_STARTED
        
        logger.info(f"[{self.name}] Initialization complete")
    
    async def subscribe_to(self, agent_name: str) -> None:
        """Subscribe to messages from another agent.
        
        Args:
            agent_name: Name of agent to subscribe to
        """
        await self.blackboard.subscribe_to_agent(self.name, agent_name)
        logger.info(f"[{self.name}] Subscribed to {agent_name}")
    
    async def read_messages(self) -> List[AgentMessage]:
        """Read messages sent to this agent.
        
        Returns:
            List of messages
        """
        messages = await self.blackboard.get_messages(self.name)
        for msg in messages:
            logger.debug(f"[{self.name}] Received message: {msg.sender} - {msg.content}")
        return messages
    
    async def post_message(
        self,
        content: Any,
        message_type: str = "info",
        recipients: Optional[List[str]] = None
    ) -> None:
        """Send message to blackboard.
        
        Args:
            content: Message content
            message_type: Message type
            recipients: List of recipients (None means broadcast)
        """
        await self.blackboard.post_message(
            sender=self.name,
            content=content,
            message_type=message_type,
            recipients=recipients
        )
    
    async def call_tool(
        self,
        tool_name: str,
        *args,
        **kwargs
    ) -> ToolExecutionResult:
        """Call a tool with execution result recording.
        
        Args:
            tool_name: Tool name
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            ToolExecutionResult
        """
        if tool_name not in self.tools:
            error_result = ToolExecutionResult(
                status="error",
                output=None,
                error=f"Tool not found: {tool_name}"
            )
            await self.record_observation(tool_name, kwargs, error_result)
            return error_result
        
        tool = self.tools[tool_name]
        logger.info(f"[{self.name}] Calling tool: {tool_name}")
        
        try:
            result = await tool.safe_execute(**kwargs)
            await self.record_observation(tool_name, kwargs, result)
            logger.debug(f"[{self.name}] Tool execution complete: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Tool execution failed: {tool_name} - {e}")
            error_result = ToolExecutionResult(
                status="error",
                output=None,
                error=str(e)
            )
            await self.record_observation(tool_name, kwargs, error_result)
            return error_result
    
    async def record_observation(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: ToolExecutionResult
    ) -> None:
        """Record tool execution observation to blackboard and local history.
        
        Args:
            tool_name: Tool name
            args: Arguments passed to tool
            result: Execution result
        """
        observation = {
            "agent": self.name,
            "tool": tool_name,
            "args": args,
            "result": result.to_dict(),
            "timestamp": asyncio.get_event_loop().time(),
        }
        
        # Add to local history
        self.observations.append(observation)
        
        # Write to blackboard
        observations = await self.blackboard.get("tool_observations", [])
        observations.append(observation)
        await self.blackboard.update("tool_observations", observations, agent_name=self.name)
        
        logger.debug(f"[{self.name}] Observation recorded: {tool_name}")
    
    async def query_llm(  # type: ignore
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        tools_context: str = ""
    ) -> str:
        """Query LLM with optional tools context.
        
        Args:
            prompt: Prompt text
            temperature: Temperature parameter
            max_tokens: Maximum tokens
            tools_context: Context about available tools
            
        Returns:
            LLM response
        """
        if not self.llm_client:
            raise ValueError(f"[{self.name}] LLM client not configured")
        
        try:
            # Build full messages
            full_system = self.system_prompt
            if tools_context:
                full_system += f"\n\nAvailable tools:\n{tools_context}"
            
            messages = [
                {"role": "system", "content": full_system},
                {"role": "user", "content": prompt}
            ]

            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            result = response.choices[0].message.content
            if result is None:
                return ""
            
            logger.debug(f"[{self.name}] LLM response length: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] LLM query failed: {e}")
            raise
    
    def parse_tool_calls(self, llm_response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from LLM response.
        
        Supports multiple formats:
        1. JSON: {"tool": "tool_name", "args": {...}}
        2. Action format: Action tool_name(args)
        3. Natural language: "I need to use the tool_name tool"
        
        Args:
            llm_response: LLM response text
            
        Returns:
            List of tool call dictionaries
        """
        tool_calls = []
        
        # Try JSON format first
        try:
            json_match = re.search(r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*\}', llm_response)
            if json_match:
                # Try to parse the full JSON object
                json_obj = json.loads(json_match.group(0))
                tool_calls.append({
                    "tool": json_obj.get("tool"),
                    "args": json_obj.get("args", {}),
                })
        except json.JSONDecodeError:
            pass
        
        # Try action format: Action tool_name(...)
        action_matches = re.findall(
            r'Action\s+(\w+)\s*\(([^)]*)\)',
            llm_response,
            re.IGNORECASE
        )
        for tool_name, args_str in action_matches:
            if tool_name in self.tools:
                # Parse arguments
                args = {}
                if args_str.strip():
                    try:
                        args = json.loads(f"{{{args_str}}}")
                    except json.JSONDecodeError:
                        # Simple key=value parsing
                        for pair in args_str.split(','):
                            if '=' in pair:
                                key, value = pair.split('=', 1)
                                args[key.strip()] = value.strip().strip('"\'')
                
                tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                })
        
        return tool_calls
    
    async def react_loop(self, task_prompt: str) -> Dict[str, Any]:
        """Execute ReAct loop: Think -> Act -> Observe -> Repeat.
        
        Args:
            task_prompt: Task description prompt
            
        Returns:
            Final result after loop completion
        """
        logger.info(f"[{self.name}] Starting ReAct loop")
        
        current_prompt = task_prompt
        final_result = {}
        last_llm_response = ""
        
        for iteration in range(self.max_iterations):
            logger.info(f"[{self.name}] ReAct iteration {iteration + 1}/{self.max_iterations}")
            
            # Build tools context
            tools_context = self._build_tools_context()
            
            # Think: Query LLM
            llm_response = await self.query_llm(
                current_prompt,
                temperature=0.3,
                tools_context=tools_context
            )
            last_llm_response = llm_response
            
            logger.debug(f"[{self.name}] LLM response: {llm_response[:200]}...")
            
            # Parse tool calls
            tool_calls = self.parse_tool_calls(llm_response)
            
            if not tool_calls:
                # No tool calls, assume task is complete
                final_result = {
                    "status": "completed",
                    "response": llm_response,
                    "iterations": iteration + 1,
                }
                logger.info(f"[{self.name}] Task completed after {iteration + 1} iterations")
                break
            
            # Act: Execute tool calls
            observations = []
            for call in tool_calls:
                tool_name = call.get("tool")
                args = call.get("args", {})
                
                if tool_name:
                    result = await self.call_tool(tool_name, **args)
                    observations.append({
                        "tool": tool_name,
                        "args": args,
                        "result": result.to_dict(),
                    })
            
            # Update prompt with observations
            current_prompt = f"""
Previous task:
{task_prompt}

Previous response:
{llm_response}

Tool execution results:
{json.dumps(observations, ensure_ascii=False, indent=2)}

Based on the above results, continue the task. If the task is complete, provide the final answer without any tool calls.
            """
        
        if not final_result:
            logger.warning(f"[{self.name}] Max iterations reached")
            final_result = {
                "status": "max_iterations_reached",
                "response": last_llm_response,
                "iterations": self.max_iterations,
            }
        
        return final_result
    
    def _build_tools_context(self) -> str:
        """Build context string describing available tools.
        
        Returns:
            Tools context string
        """
        context_lines = []
        context_lines.append(f"Available tools ({len(self.tools)}):")
        
        for tool_name, tool in self.tools.items():
            context_lines.append(f"\n- {tool_name}: {tool.description}")
            
            if tool.args_schema:
                context_lines.append("  Arguments:")
                for arg_name, arg_def in tool.args_schema.items():
                    required = "(required)" if arg_def.required else f"(optional, default: {arg_def.default})"
                    context_lines.append(f"    - {arg_name} ({arg_def.type.__name__}) {required}: {arg_def.description}")
        
        return "\n".join(context_lines)
    
    @abstractmethod
    async def process(self) -> Dict[str, Any]:
        """Core processing logic for agent (must be implemented by subclass).
        
        Returns:
            Processing result dictionary
        """
        raise NotImplementedError(f"[{self.name}] process() method must be implemented by subclass")
    
    async def run(self) -> Dict[str, Any]:
        """Run agent's main workflow.
        
        Workflow:
        1. Update status to "running"
        2. Read messages
        3. Call process() to handle tasks
        4. Send result messages
        5. Update status to "completed"
        
        Returns:
            Processing result
        """
        logger.info(f"[{self.name}] Starting execution...")
        
        try:
            self.status = AgentStatus.RUNNING
            await self.blackboard.update_agent_status(self.name, AgentStatus.RUNNING)
            
            # Read messages
            messages = await self.read_messages()
            if messages:
                logger.info(f"[{self.name}] Processing {len(messages)} messages")
            
            # Execute processing logic
            result = await self.process()
            
            # Send result
            await self.post_message(result, message_type="result")
            
            # Update status
            self.status = AgentStatus.COMPLETED
            await self.blackboard.update_agent_status(self.name, AgentStatus.COMPLETED)
            
            logger.info(f"[{self.name}] Execution complete")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] Execution failed: {e}", exc_info=True)
            
            self.status = AgentStatus.FAILED
            await self.blackboard.update_agent_status(self.name, AgentStatus.FAILED)
            
            await self.post_message(
                {"error": str(e)},
                message_type="error"
            )
            
            raise
