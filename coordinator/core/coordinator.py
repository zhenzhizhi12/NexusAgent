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
    基于黑板架构的多智能体协调器。
    
    架构特点：
    1. 多个专业Agent协同工作
    2. 通过共享黑板进行状态管理和消息传递
    3. 异步执行，支持Agent间并行协作
    4. 完整的消息追踪和历史记录
    
    Agent角色：
    - ArchitectAgent (L0): 需求分析与技术设计
    - KnowledgeExpertAgent (L1-L3): 知识检索与推理
    - CangjieEngineerAgent: 代码生成与依赖配置
    - DevOpsQAAgent: 构建、测试与迭代
    
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
        
        # 路径配置
        self.build_script_path = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "scripts" / "build.ps1"
        self.evolution_path = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "Evolution.md"
        
        # 初始化所有Agent
        self._initialize_agents()
        
        # 如果有项目根目录，配置到黑板
        if project_root:
            asyncio.run(self.blackboard.update("project_root", str(project_root), agent_name="system"))
    
    def _initialize_agents(self) -> None:
        初始化所有专业Agent。
        
        logger.info("初始化Agents...")
        
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
        
        logger.info(f"初始化完成，共 {len(self.agents)} 个Agent")
    
    async def initialize_all_agents(self) -> None:
        初始化所有Agent（注册工具、更新状态等）。
        
        logger.info("初始化所有Agent...")
        
        tasks = [agent.initialize() for agent in self.agents.values()]
        await asyncio.gather(*tasks)
        
        logger.info("所有Agent初始化完成")
    
    async def setup_agent_communication(self) -> None:
        设置Agent间的消息订阅关系。
        
        logger.info("设置Agent通信...")
        
        # KnowledgeExpert订阅Architect
        await self.agents["KnowledgeExpertAgent"].subscribe_to("ArchitectAgent")
        
        # CangjieEngineer订阅Architect和KnowledgeExpert
        await self.agents["CangjieEngineerAgent"].subscribe_to("ArchitectAgent")
        await self.agents["CangjieEngineerAgent"].subscribe_to("KnowledgeExpertAgent")
        
        # DevOpsQA订阅CangjieEngineer
        await self.agents["DevOpsQAAgent"].subscribe_to("CangjieEngineerAgent")
        
        logger.info("Agent通信设置完成")
    
    async def run_workflow(self, requirement: str) -> Dict[str, Any]:
        运行完整的多Agent工作流。
        
        执行顺序：
        1. ArchitectAgent: 需求分析
        2. KnowledgeExpertAgent: 知识检索
        3. CangjieEngineerAgent: 代码生成
        4. DevOpsQAAgent: 构建测试
        
        Args:
            requirement: 用户需求
            
        Returns:
            工作流执行结果
        logger.info("=" * 80)
        logger.info("MultiAgentCoordinator - 开始执行工作流")
        logger.info("=" * 80)
        logger.info(f"用户需求: {requirement}")
        
        final_results = {
            "requirement": requirement,
            "agent_results": {},
            "success": False,
            "errors": [],
        }
        
        try:
            # 写入需求到黑板
            await self.blackboard.update("requirement", requirement, agent_name="system")
            
            # 初始化所有Agent
            await self.initialize_all_agents()
            
            # 设置通信
            await self.setup_agent_communication()
            
            # 执行工作流（顺序执行）
            execution_order = [
                "ArchitectAgent",
                "KnowledgeExpertAgent",
                "CangjieEngineerAgent",
                "DevOpsQAAgent",
            ]
            
            for agent_name in execution_order:
                logger.info(f"--- 执行 {agent_name} ---")
                
                agent = self.agents[agent_name]
                
                try:
                    result = await agent.run()
                    final_results["agent_results"][agent_name] = result
                    
                    if not result.get("success"):
                        warning_msg = f"{agent_name} 执行失败: {result.get('error', '未知错误')}"
                        logger.warning(warning_msg)
                        final_results["errors"].append(warning_msg)
                except Exception as e:
                    error_msg = f"{agent_name} 执行异常: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    final_results["errors"].append(error_msg)
                    final_results["agent_results"][agent_name] = {
                        "success": False,
                        "error": str(e),
                    }
            
            # 检查所有Agent是否成功
            all_success = all(
                final_results["agent_results"].get(agent_name, {}).get("success", False)
                for agent_name in execution_order
            )
            
            final_results["success"] = all_success
            
            if all_success:
                logger.info("=" * 80)
                logger.info("工作流执行成功")
                logger.info("=" * 80)
            else:
                logger.warning("=" * 80)
                logger.info("工作流执行完成，但部分Agent失败")
                logger.info("=" * 80)
        
        except Exception as e:
            logger.error(f"工作流执行失败: {e}", exc_info=True)
            final_results["success"] = False
            final_results["errors"].append(str(e))
        
        return final_results
    
    async def get_state_snapshot(self) -> Dict[str, Any]:
        获取当前黑板状态快照。
        
        Returns:
            状态快照
        return await self.blackboard.get_state_snapshot()
    
    async def export_execution_history(self, filepath: Path) -> None:
        导出执行历史到JSON文件。
        
        Args:
            filepath: 输出文件路径
        await self.blackboard.export_to_json(filepath)
    
    async def reset(self) -> None:
        重置所有状态（用于测试）。
        
        await self.blackboard.reset()
        
        for agent in self.agents.values():
            agent.status = AgentStatus.Agent未开始
        
        logger.info("Coordinator已重置")


async def execute_multi_agent_workflow(
    requirement: str,
    search_engine=None,
    project_root: Optional[Path] = None
) -> Dict[str, Any]:
    便捷函数：执行多Agent工作流。
    
    Args:
        requirement: 用户需求
        search_engine: 搜索引擎实例
        project_root: 项目根目录
        
    Returns:
        执行结果
    配置LLM客户端
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    llm_client = OpenAI(base_url=BASE_URL, api_key=api_key) if api_key else None
    
    # 创建协调器
    coordinator = MultiAgentCoordinator(
        search_engine=search_engine,
        project_root=project_root,
        llm_client=llm_client
    )
    
    # 运行工作流
    result = await coordinator.run_workflow(requirement)
    
    return result
