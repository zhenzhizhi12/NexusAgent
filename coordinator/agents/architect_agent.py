import logging
import re
from typing import Any, Dict, List

from coordinator.agents.base_agent import BaseAgent, Tool
from coordinator.core.blackboard import GlobalState

logger = logging.getLogger("ArchitectAgent")


class RequirementAnalysisTool(Tool):
    需求分析工具。
    
    def __init__(self):
        super().__init__(name="requirement_analysis", description="分析用户需求，拆解为UI组件、数据结构、交互方式")
    
    async def execute(self, requirement: str) -> Dict[str, Any]:
        执行需求分析。
        
        Args:
            requirement: 用户需求描述
            
        Returns:
            分析结果
        result = {
            "requirement": requirement,
            "problem_type": "",
            "ui_components": [],
            "data_structures": [],
            "technical_keywords": [],
            "implementation_points": [],
        }
        
        # 简单的关键词提取
        ui_keywords = {
            "登录": "LoginComponent",
            "列表": "ListContainer",
            "按钮": "Button",
            "输入框": "TextInput",
            "卡片": "Card",
            "图片": "Image",
            "导航": "Navigator",
            "页面": "Page",
        }
        
        data_keywords = {
            "数据": "DataModel",
            "用户": "UserModel",
            "列表": "ListData",
            "分页": "Pagination",
            "状态": "State",
        }
        
        # 搜索UI组件
        for keyword, component in ui_keywords.items():
            if keyword in requirement:
                result["ui_components"].append({
                    "关键词": keyword,
                    "组件": component,
                })
                result["technical_keywords"].append(component)
        
        # 搜索数据结构
        for keyword, model in data_keywords.items():
            if keyword in requirement:
                result["data_structures"].append({
                    "关键词": keyword,
                    "数据结构": model,
                })
                result["technical_keywords"].append(model)
        
        # 判断问题类型
        if "登录" in requirement:
            result["problem_type"] = "认证相关"
        elif "列表" in requirement:
            result["problem_type"] = "数据展示"
        elif "表单" in requirement:
            result["problem_type"] = "数据输入"
        else:
            result["problem_type"] = "通用功能"
        
        # 生成技术实现点
        if result["ui_components"]:
            result["implementation_points"].append("使用ArkUI构建UI组件")
        if result["data_structures"]:
            result["implementation_points"].append("设计合理的数据模型")
        result["implementation_points"].append("实现业务逻辑")
        result["implementation_points"].append("处理用户交互")
        
        logger.info(f"需求分析完成: {result['problem_type']}, {len(result['ui_components'])}个UI组件")
        
        return result


class ArchitectAgent(BaseAgent):
    架构师Agent（L0）。
    
    职责：
    1. 持有harmonyos-requirement-analysis技能
    2. 负责需求拆解和问题分析
    3. 输出UI组件、数据结构、技术实现点
    
    输入：用户需求
    输出：技术分析结果（写入黑板）
    
    def __init__(self, blackboard: GlobalState, llm_client=None, llm_model="Pro/zai-org/GLM-5"):
        system_prompt = 你是鸿蒙应用开发架构师，负责需求分析和技术方案设计。

你的能力：
1. 理解用户需求，拆解为功能模块
2. 识别所需的UI组件（ArkUI组件）
3. 设计合理的数据结构
4. 提炼技术实现点和关键技术

工作流程：
1. 接收用户需求
2. 分析需求，识别问题类型（认证/数据展示/数据输入/通用功能等）
3. 拆解UI组件（按钮、列表、输入框、卡片等）
4. 设计数据结构（UserModel、DataModel等）
5. 提炼技术关键词和实现点
6. 输出结构化的技术分析方案

输出格式：
{
  "requirement": "原始需求",
  "problem_type": "问题类型",
  "ui_components": [{"关键词": "...", "组件": "..."}],
  "data_structures": [{"关键词": "...", "数据结构": "..."}],
  "technical_keywords": ["组件名", "数据结构名"],
  "implementation_points": ["实现点1", "实现点2"]
}

注意：
- 技术关键词要准确对应鸿蒙ArkUI组件和仓颉语言特性
- 实现点要包含UI设计和业务逻辑
- 为后续Agent提供清晰的技术指导
        
        super().__init__(
            name="ArchitectAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
    
    async def register_tools(self) -> None:
        注册工具。
        
        await super().register_tools()
        self.add_tool(RequirementAnalysisTool())
    
    async def process(self) -> Dict[str, Any]:
        执行需求分析。
        
        Returns:
            分析结果
        logger.info(f"[{self.name}] 开始需求分析...")
        
        # 从黑板获取需求
        requirement = await self.blackboard.get("requirement")
        
        if not requirement:
            raise ValueError(f"[{self.name}] 黑板上没有找到需求信息")
        
        # 使用工具进行分析
        analysis_result = await self.call_tool("requirement_analysis", requirement)
        
        # 将结果写入黑板
        await self.blackboard.update("technical_analysis", analysis_result, agent_name=self.name)
        
        # 也可以使用LLM增强分析
        if self.llm_client:
            try:
                llm_prompt = f"""
基于以下需求分析结果，提供更详细的技术建议：

需求: {requirement}

分析结果:
{analysis_result}

请提供：
1. 推荐的ArkUI组件具体用法
2. 数据结构的详细设计
3. 技术实现的最佳实践建议
                """
                
                llm_result = await self.query_llm(llm_prompt, temperature=0.4)
                analysis_result["llm_recommendations"] = llm_result
                await self.blackboard.update("technical_analysis", analysis_result, agent_name=self.name)
                
            except Exception as e:
                logger.warning(f"[{self.name}] LLM增强分析失败: {e}")
        
        logger.info(f"[{self.name}] 需求分析完成，问题类型: {analysis_result.get('problem_type', '未知')}")
        
        return {
            "agent": self.name,
            "success": True,
            "result": analysis_result,
        }
