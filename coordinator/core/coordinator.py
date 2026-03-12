"""
Multi-Agent Coordinator

Orchestrates multiple agents for HarmonyOS development workflow.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from coordinator.core.blackboard import GlobalState, AgentStatus
from coordinator.agents.base_agent import BaseAgent
from coordinator.agents.architect_agent import ArchitectAgent
from coordinator.agents.knowledge_agent import KnowledgeExpertAgent
from coordinator.agents.engineer_agent import CangjieEngineerAgent
from coordinator.agents.devops_agent import DevOpsQAAgent

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("MultiAgentCoordinator")

BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "Pro/zai-org/GLM-5"


class MultiAgentCoordinator:
    """Multi-agent coordinator based on blackboard architecture.
    
    Architecture features:
    1. Multiple specialized agents work together
    2. State management and message passing through shared blackboard
    3. Asynchronous execution supporting parallel agent collaboration
    4. Complete message tracing and history recording
    
    Agent roles:
    - ArchitectAgent (L0): Requirement analysis and technical design
    - KnowledgeExpertAgent (L1-L3): Knowledge retrieval and reasoning
    - CangjieEngineerAgent: Code generation and dependency configuration
    - DevOpsQAAgent: Build, test, and iteration
    """
    
    def __init__(
        self,
        search_engine=None,
        project_root: Optional[Path] = None,
        llm_client: Optional[OpenAI] = None,
        llm_model: str = MODEL
    ):
        self.blackboard = GlobalState()
        self.agents: Dict[str, BaseAgent] = {}
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.search_engine = search_engine
        
        # Path configuration
        self.build_script_path = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "scripts" / "build.ps1"
        self.evolution_path = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "Evolution.md"
        
        # Initialize all agents
        self._initialize_agents()
        
        # If project root exists, configure to blackboard
        if project_root:
            asyncio.run(self.blackboard.update("project_root", str(project_root), agent_name="system"))
    
    def _initialize_agents(self) -> None:
        """Initialize all specialized agents."""
        logger.info("Initializing agents...")
        
        self.agents["ArchitectAgent"] = ArchitectAgent(
            blackboard=self.blackboard,
            llm_client=self.llm_client,
            llm_model=self.llm_model
        )
        
        self.agents["KnowledgeExpertAgent"] = KnowledgeExpertAgent(
            blackboard=self.blackboard,
            search_engine=self.search_engine,
            llm_client=self.llm_client,
            llm_model=self.llm_model
        )
        
        self.agents["CangjieEngineerAgent"] = CangjieEngineerAgent(
            blackboard=self.blackboard,
            llm_client=self.llm_client,
            llm_model=self.llm_model
        )
        
        self.agents["DevOpsQAAgent"] = DevOpsQAAgent(
            blackboard=self.blackboard,
            build_script_path=self.build_script_path,
            evolution_path=self.evolution_path,
            llm_client=self.llm_client,
            llm_model=self.llm_model
        )
        
        logger.info(f"Initialization completed, total {len(self.agents)} agents")
    
    async def initialize_all_agents(self) -> None:
        """Initialize all agents (register tools, update status, etc.)."""
        logger.info("Initializing all agents...")
        
        tasks = [agent.initialize() for agent in self.agents.values()]
        await asyncio.gather(*tasks)
        
        logger.info("All agents initialized")
    
    async def setup_agent_communication(self) -> None:
        """Setup message subscription relationships between agents."""
        logger.info("Setting up agent communication...")
        
        # KnowledgeExpert subscribes to Architect
        await self.agents["KnowledgeExpertAgent"].subscribe_to("ArchitectAgent")
        
        # CangjieEngineer subscribes to Architect and KnowledgeExpert
        await self.agents["CangjieEngineerAgent"].subscribe_to("ArchitectAgent")
        await self.agents["CangjieEngineerAgent"].subscribe_to("KnowledgeExpertAgent")
        
        # DevOpsQA subscribes to CangjieEngineer
        await self.agents["DevOpsQAAgent"].subscribe_to("CangjieEngineerAgent")
        
        logger.info("Agent communication setup completed")
    
    async def run_workflow(self, requirement: str) -> Dict[str, Any]:
        """Run complete multi-agent workflow.
        
        Execution order:
        1. ArchitectAgent: Requirement analysis
        2. KnowledgeExpertAgent: Knowledge retrieval
        3. CangjieEngineerAgent: Code generation
        4. DevOpsQAAgent: Build and test
        
        Args:
            requirement: User requirement
            
        Returns:
            Workflow execution result
        """
        logger.info("=" * 80)
        logger.info("MultiAgentCoordinator - Starting workflow execution")
        logger.info("=" * 80)
        logger.info(f"User requirement: {requirement}")
        
        final_results = {
            "requirement": requirement,
            "agent_results": {},
            "success": False,
            "errors": [],
        }
        
        try:
            # Write requirement to blackboard
            await self.blackboard.update("requirement", requirement, agent_name="system")
            
            # Initialize all agents
            await self.initialize_all_agents()
            
            # Setup communication
            await self.setup_agent_communication()
            
            # Execute workflow (sequential execution)
            execution_order = [
                "ArchitectAgent",
                "KnowledgeExpertAgent",
                "CangjieEngineerAgent",
                "DevOpsQAAgent",
            ]
            
            for agent_name in execution_order:
                logger.info(f"--- Executing {agent_name} ---")
                
                agent = self.agents[agent_name]
                
                try:
                    result = await agent.run()
                    final_results["agent_results"][agent_name] = result
                    
                    if not result.get("success"):
                        warning_msg = f"{agent_name} execution failed: {result.get('error', 'Unknown error')}"
                        logger.warning(warning_msg)
                        final_results["errors"].append(warning_msg)
                except Exception as e:
                    error_msg = f"{agent_name} execution exception: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    final_results["errors"].append(error_msg)
                    final_results["agent_results"][agent_name] = {
                        "success": False,
                        "error": str(e),
                    }
            
            # Check if all agents succeeded
            all_success = all(
                final_results["agent_results"].get(agent_name, {}).get("success", False)
                for agent_name in execution_order
            )
            
            final_results["success"] = all_success
            
            if all_success:
                logger.info("=" * 80)
                logger.info("Workflow execution successful")
                logger.info("=" * 80)
            else:
                logger.warning("=" * 80)
                logger.info("Workflow execution completed, but some agents failed")
                logger.info("=" * 80)
        
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            final_results["success"] = False
            final_results["errors"].append(str(e))
        
        return final_results
    
    async def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current blackboard state snapshot.
        
        Returns:
            State snapshot
        """
        return await self.blackboard.get_state_snapshot()
    
    async def export_execution_history(self, filepath: Path) -> None:
        """Export execution history to JSON file.
        
        Args:
            filepath: Output file path
        """
        await self.blackboard.export_to_json(filepath)
    
    async def reset(self) -> None:
        """Reset all state (for testing)."""
        await self.blackboard.reset()
        
        for agent in self.agents.values():
            agent.status = AgentStatus.NOT_STARTED
        
        logger.info("Coordinator has been reset")


async def execute_multi_agent_workflow(
    requirement: str,
    search_engine=None,
    project_root: Optional[Path] = None
) -> Dict[str, Any]:
    """Convenience function: Execute multi-agent workflow.
    
    Args:
        requirement: User requirement
        search_engine: Search engine instance
        project_root: Project root path
        
    Returns:
        Execution result
    """
    # Configure LLM client
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    llm_client = OpenAI(base_url=BASE_URL, api_key=api_key) if api_key else None
    
    # Create coordinator
    coordinator = MultiAgentCoordinator(
        search_engine=search_engine,
        project_root=project_root,
        llm_client=llm_client
    )
    
    # Run workflow
    result = await coordinator.run_workflow(requirement)
    
    return result
