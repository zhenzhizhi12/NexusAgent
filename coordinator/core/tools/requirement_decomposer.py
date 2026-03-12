"""
Requirement Decomposer Tool

Decompose user requirements into structured components:
- Business logic
- UI components
- Data structures
- Technical keywords
- Implementation points
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from coordinator.core.tool import BaseTool, ToolExecutionResult, ToolArgument


logger = logging.getLogger("RequirementDecomposerTool")


class RequirementDecomposerTool(BaseTool):
    """Decompose requirements into structured components.
    
    Features:
    - Extract business logic requirements
    - Identify UI components
    - Design data structures
    - Extract technical keywords
    - Generate implementation points
    - Problem type classification
    """
    
    def __init__(self):
        """Initialize the requirement decomposer tool."""
        super().__init__(
            name="requirement_decomposer",
            description="Decompose requirements into business logic, UI components, and data structures",
            args_schema={
                "requirement": ToolArgument(
                    name="requirement",
                    type=str,
                    description="User requirement text to decompose"
                ),
                "enhanced_analysis": ToolArgument(
                    name="enhanced_analysis",
                    type=bool,
                    description="Enable enhanced keyword extraction (default: True)",
                    required=False,
                    default=True
                ),
            }
        )
        
        # Predefined component mappings
        self.ui_component_map = {
            "登录": "LoginComponent",
            "注册": "RegisterComponent",
            "按钮": "Button",
            "列表": "ListContainer",
            "输入框": "TextInput",
            "文本框": "TextArea",
            "卡片": "Card",
            "图片": "Image",
            "导航": "Navigator",
            "页面": "Page",
            "标签": "Tabs",
            "表单": "Form",
            "对话框": "AlertDialog",
            "下拉框": "Select",
            "滑动条": "Slider",
            "开关": "Toggle",
            "时间选择器": "DatePicker",
            "表格": "Grid",
            "菜单": "Menu",
            "手势": "Gesture",
            "滚动": "Scroll",
        }
        
        self.data_structure_map = {
            "用户": "UserModel",
            "数据": "DataModel",
            "列表": "ListData",
            "分页": "PaginationModel",
            "状态": "State",
            "配置": "Config",
            "订单": "OrderModel",
            "商品": "ProductModel",
            "消息": "MessageModel",
            "日志": "LogModel",
        }
        
        self.problem_type_patterns = {
            "认证相关": ["登录", "注册", "认证", "验证", "权限", "安全"],
            "数据展示": ["列表", "表格", "展示", "查看", "浏览", "检索"],
            "数据输入": ["表单", "输入", "提交", "编辑", "创建", "添加"],
            "交互操作": ["点击", "拖拽", "滑动", "手势", "交互"],
            "数据处理": ["计算", "转换", "处理", "分析", "统计"],
            "网络通信": ["请求", "上传", "下载", "通信", "同步"],
            "通用功能": ["功能", "模块", "系统"],
        }
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Decompose requirement into structured components."""
        requirement = kwargs.get("requirement", "")
        enhanced_analysis = kwargs.get("enhanced_analysis", True)
        
        metadata = {
            "requirement_length": len(requirement),
            "enhanced_analysis": enhanced_analysis,
        }
        
        try:
            result = {
                "requirement": requirement,
                "problem_type": "",
                "ui_components": [],
                "data_structures": [],
                "business_logic": [],
                "technical_keywords": [],
                "implementation_points": [],
            }
            
            # Step 1: Identify problem type
            result["problem_type"] = self._classify_problem_type(requirement)
            
            # Step 2: Extract UI components
            result["ui_components"] = self._extract_ui_components(requirement)
            
            # Step 3: Extract data structures
            result["data_structures"] = self._extract_data_structures(requirement)
            
            # Step 4: Extract business logic
            result["business_logic"] = self._extract_business_logic(requirement)
            
            # Step 5: Compile technical keywords
            result["technical_keywords"] = self._compile_technical_keywords(result)
            
            # Step 6: Generate implementation points
            result["implementation_points"] = self._generate_implementation_points(result)
            
            metadata.update({
                "ui_components_count": len(result["ui_components"]),
                "data_structures_count": len(result["data_structures"]),
                "business_logic_count": len(result["business_logic"]),
                "technical_keywords_count": len(result["technical_keywords"]),
            })
            
            logger.info(f"[RequirementDecomposer] Decomposed requirement: {result['problem_type']}")
            return ToolExecutionResult(
                status="success",
                output=result,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"[RequirementDecomposer] Decomposition failed: {e}", exc_info=True)
            return ToolExecutionResult(
                status="error",
                output=None,
                error=str(e),
                metadata=metadata
            )
    
    def _classify_problem_type(self, requirement: str) -> str:
        """Classify the problem type based on keywords."""
        for problem_type, keywords in self.problem_type_patterns.items():
            for keyword in keywords:
                if keyword in requirement:
                    return problem_type
        return "通用功能"
    
    def _extract_ui_components(self, requirement: str) -> List[Dict[str, str]]:
        """Extract UI components from requirement."""
        components = []
        for keyword, component in self.ui_component_map.items():
            if keyword in requirement:
                components.append({
                    "关键词": keyword,
                    "组件": component,
                })
        return components
    
    def _extract_data_structures(self, requirement: str) -> List[Dict[str, str]]:
        """Extract data structures from requirement."""
        structures = []
        for keyword, model in self.data_structure_map.items():
            if keyword in requirement:
                structures.append({
                    "关键词": keyword,
                    "数据结构": model,
                })
        return structures
    
    def _extract_business_logic(self, requirement: str) -> List[str]:
        """Extract business logic requirements."""
        logic_points = []
        
        # Common business logic patterns
        patterns = [
            r"需要(.*?)(?:功能|逻辑|处理)",
            r"实现(.*?)(?:功能|逻辑)",
            r"支持(.*?)(?:操作|功能)",
            r"能够(.*?)(?:功能|逻辑|处理)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, requirement)
            for match in matches:
                if len(match.strip()) > 0:
                    logic_points.append(f"{match.strip()}相关业务逻辑")
        
        # Extract from common phrases
        phrases = [
            "用户交互", "数据验证", "状态管理", "事件处理",
            "数据持久化", "网络请求", "错误处理", "日志记录"
        ]
        
        for phrase in phrases:
            if phrase in requirement:
                logic_points.append(f"{phrase}逻辑")
        
        return list(set(logic_points))
    
    def _compile_technical_keywords(self, result: Dict[str, Any]) -> List[str]:
        """Compile technical keywords from extracted components."""
        keywords = set()
        
        # Add UI component names
        for comp in result.get("ui_components", []):
            keywords.add(comp.get("组件", ""))
        
        # Add data structure names
        for ds in result.get("data_structures", []):
            keywords.add(ds.get("数据结构", ""))
        
        # Add common technical terms
        tech_terms = [
            "ArkUI", "仓颉", "Cangjie", "state", "lifecycle",
            "callback", "Observer", "Subscriber", "Publisher"
        ]
        keywords.update(tech_terms)
        
        return sorted(list(keywords))
    
    def _generate_implementation_points(self, result: Dict[str, Any]) -> List[str]:
        """Generate implementation points based on analysis."""
        points = []
        
        if result.get("ui_components"):
            points.append("使用ArkUI构建UI组件")
        
        if result.get("data_structures"):
            points.append("设计合理的数据模型")
        
        if result.get("business_logic"):
            points.append("实现业务逻辑处理")
            points.append("处理用户交互事件")
        
        # Add problem-specific points
        problem_type = result.get("problem_type", "")
        if "认证" in problem_type:
            points.append("实现用户认证流程")
            points.append("处理权限验证")
        elif "数据展示" in problem_type:
            points.append("实现数据加载和展示")
            points.append("支持数据刷新和分页")
        elif "数据输入" in problem_type:
            points.append("实现表单验证")
            points.append("处理数据提交")
        
        # Add generic points
        points.extend([
            "实现状态管理",
            "添加错误处理机制",
            "优化用户体验"
        ])
        
        return list(set(points))
    
    def format_for_skillet(self, decomposed: Dict[str, Any]) -> str:
        """Format decomposed requirement for SKILL.md output.
        
        Args:
            decomposed: Decomposed requirement result
            
        Returns:
            Formatted string
        """
        lines = []
        lines.append("# 需求拆解结果")
        lines.append(f"## 原始需求")
        lines.append(decomposed.get("requirement", ""))
        lines.append(f"## 问题类型")
        lines.append(decomposed.get("problem_type", ""))
        lines.append(f"## UI组件")
        for comp in decomposed.get("ui_components", []):
            lines.append(f"- {comp['关键词']}: {comp['组件']}")
        lines.append(f"## 数据结构")
        for ds in decomposed.get("data_structures", []):
            lines.append(f"- {ds['关键词']}: {ds['数据结构']}")
        lines.append(f"## 业务逻辑")
        for logic in decomposed.get("business_logic", []):
            lines.append(f"- {logic}")
        lines.append(f"## 技术关键词")
        lines.append(f"{', '.join(decomposed.get('technical_keywords', []))}")
        lines.append(f"## 实现点")
        for point in decomposed.get("implementation_points", []):
            lines.append(f"- {point}")
        
        return "\n".join(lines)
