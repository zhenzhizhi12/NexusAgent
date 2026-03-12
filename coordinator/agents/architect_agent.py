"""
Architect Agent (L0)

Responsible for requirement analysis and technical design.
Holds harmonyos-requirement-analysis skill.
"""

import logging
import re
from typing import Any, Dict, List

from coordinator.agents.base_agent import BaseAgent
from coordinator.core.blackboard import GlobalState
from coordinator.core.tools import RequirementDecomposerTool

logger = logging.getLogger("ArchitectAgent")


class ArchitectAgent(BaseAgent):
    """Architect Agent (L0).
    
    Responsibilities:
    1. Holds harmonyos-requirement-analysis skill
    2. Responsible for requirement decomposition and problem analysis
    3. Output UI components, data structures, technical implementation points
    
    Input: User requirements
    Output: Technical analysis results (written to blackboard)
    """
    
    def __init__(
        self,
        blackboard: GlobalState,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = """You are a HarmonyOS application development architect, responsible for requirement analysis and technical solution design.

Your capabilities:
1. Understand user requirements and decompose them into functional modules
2. Identify required UI components (ArkUI components)
3. Design reasonable data structures
4. Extract technical keywords and implementation points

Workflow:
1. Receive user requirements
2. Analyze requirements and identify problem types (authentication/data display/data input/general functions, etc.)
3. Decompose UI components (buttons, lists, input boxes, cards, etc.)
4. Design data structures (UserModel, DataModel, etc.)
5. Extract technical keywords and implementation points
6. Output structured technical analysis solutions

Output format:
{
  "requirement": "Original requirement",
  "problem_type": "Problem type",
  "ui_components": [{"keyword": "...", "component": "..."}],
  "data_structures": [{"keyword": "...", "data_structure": "..."}],
  "technical_keywords": ["component name", "data structure name"],
  "implementation_points": ["implementation point 1", "implementation point 2"]
}

Note:
- Technical keywords should accurately correspond to HarmonyOS ArkUI components and Cangjie language features
- Implementation points should include UI design and business logic
- Provide clear technical guidance for subsequent Agents
"""
        
        super().__init__(
            name="ArchitectAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        # Initialize tools
        self.requirement_decomposer = RequirementDecomposerTool()
    
    async def register_tools(self) -> None:
        """Register tools."""
        await super().register_tools()
        logger.info(f"[{self.name}] Tools registered")
    
    async def process(self) -> Dict[str, Any]:
        """Execute requirement analysis with skip logic."""
        logger.info(f"[{self.name}] Starting requirement analysis...")
        
        # Get requirement from blackboard
        requirement = await self.blackboard.get("requirement")
        
        # Smart skip: Check if requirement is empty or too short
        if not requirement or len(requirement.strip()) < 5:
            logger.warning(f"[{self.name}] Requirement is empty or too short, skipping analysis")
            return {
                "agent": self.name,
                "success": True,
                "skipped": True,
                "reason": "Empty or too short requirement",
                "result": None
            }
        
        # Use requirement decomposer tool
        decompose_result = await self.requirement_decomposer.execute(
            requirement=requirement,
            enhanced_analysis=True
        )
        
        if decompose_result.status != "success":
            raise ValueError(f"[{self.name}] Requirement decomposition failed: {decompose_result.error}")
        
        analysis_result = decompose_result.output
        
        # Smart skip: Check if analysis is empty (no components or structures found)
        component_count = len(analysis_result.get("ui_components", []))
        structure_count = len(analysis_result.get("data_structures", []))
        
        if component_count == 0 and structure_count == 0:
            logger.warning(f"[{self.name}] Analysis found no UI components or data structures, may be invalid request")
            analysis_result["warning"] = "No valid components or structures detected"
        
        # Write to blackboard
        await self.blackboard.update("technical_analysis", analysis_result, agent_name=self.name)
        
        # Use LLM for enhanced analysis (conditional)
        if self.llm_client and component_count + structure_count > 0:
            try:
                llm_prompt = f"""
Based on the following requirement analysis results, provide more detailed technical recommendations:

Requirement: {requirement}

Analysis results:
{analysis_result}

Please provide:
1. Recommended specific usage of ArkUI components
2. Detailed design of data structures
3. Best practice recommendations for technical implementation
"""
                
                llm_result = await self.query_llm(llm_prompt, temperature=0.4)
                analysis_result["llm_recommendations"] = llm_result
                await self.blackboard.update("technical_analysis", analysis_result, agent_name=self.name)
                
            except Exception as e:
                logger.warning(f"[{self.name}] LLM enhanced analysis failed: {e}")
        
        logger.info(f"[{self.name}] Requirement analysis completed, problem type: {analysis_result.get('problem_type', 'unknown')}")
        
        return {
            "agent": self.name,
            "success": True,
            "result": analysis_result,
        }
