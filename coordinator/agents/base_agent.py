import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from coordinator.core.blackboard import GlobalState, AgentStatus, AgentMessage

logger = logging.getLogger("BaseAgent")


class Tool(ABC):
    """Base class for Agent tools.

    Each tool is a callable functional unit that agents use to perform specific operations.
    """

    def __init__(self, name: str, description: str):
        """Initialize tool.

        Args:
            name: Tool name
            description: Tool description
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute tool functionality.

        Returns:
            Execution result
        """
        pass


class BaseAgent(ABC):
    """Base class for all multi-agents.

    All specialized agents must inherit from this class and implement:
    - name: Unique agent identifier
    - system_prompt: Corresponding SKILL.md content
    - tools: List of available tools
    - process(): Core processing logic

    Workflow:
    1. Initialize: Connect to blackboard (GlobalState)
    2. Subscribe: Subscribe to messages from other agents
    3. Execute: Complete specialized tasks via process() method
    4. Communicate: Send results via blackboard's post_message
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        blackboard: GlobalState,
        llm_client: Optional[OpenAI] = None,
        llm_model: str = "Pro/zai-org/GLM-5"
    ):
        """Initialize agent.

        Args:
            name: Agent name
            system_prompt: System prompt from SKILL.md
            blackboard: Global state blackboard
            llm_client: OpenAI client (optional)
            llm_model: LLM model name
        """
        self.name = name
        self.system_prompt = system_prompt
        self.blackboard = blackboard
        self.llm_client = llm_client
        self.llm_model = llm_model

        self.tools: Dict[str, Tool] = {}
        self.status = AgentStatus.NOT_STARTED

        logger.info(f"Agent initialized: {name}")

    def add_tool(self, tool: Tool) -> None:
        """Add tool to agent.

        Args:
            tool: Tool instance
        """
        self.tools[tool.name] = tool
        logger.debug(f"[{self.name}] Added tool: {tool.name}")

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

    async def post_message(self, content: Any, message_type: str = "info") -> None:
        """Send message to blackboard.

        Args:
            content: Message content
            message_type: Message type
        """
        await self.blackboard.post_message(
            sender=self.name,
            content=content,
            message_type=message_type
        )

    async def call_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Call a tool.

        Args:
            tool_name: Tool name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Tool execution result

        Raises:
            ValueError: Tool does not exist
        """
        if tool_name not in self.tools:
            raise ValueError(f"[{self.name}] Tool not found: {tool_name}")

        tool = self.tools[tool_name]
        logger.info(f"[{self.name}] Calling tool: {tool_name}")

        try:
            result = await tool.execute(*args, **kwargs)
            logger.debug(f"[{self.name}] Tool execution complete: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"[{self.name}] Tool execution failed: {tool_name} - {e}")
            raise

    async def query_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """Query LLM (if client is configured).

        Args:
            prompt: Prompt text
            temperature: Temperature parameter

        Returns:
            LLM response
        """
        if not self.llm_client:
            raise ValueError(f"[{self.name}] LLM client not configured")

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=2000,
            )

            result = response.choices[0].message.content
            if result is None:
                return ""

            logger.debug(f"[{self.name}] LLM response length: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"[{self.name}] LLM query failed: {e}")
            raise

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
