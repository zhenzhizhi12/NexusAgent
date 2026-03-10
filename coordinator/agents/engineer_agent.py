import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from coordinator.agents.base_agent import BaseAgent, Tool
from coordinator.core.blackboard import GlobalState

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("CangjieEngineerAgent")


class CodeGenerationTool(Tool):
    代码生成工具。
    
    def __init__(self):
        super().__init__(name="code_generation", description="基于需求分析和知识检索生成仓颉代码")
    
    async def execute(self, analysis: Dict, knowledge: Dict) -> str:
        执行代码生成。
        
        Args:
            analysis: 需求分析结果
            knowledge: 知识检索结果
            
        Returns:
            生成的代码
        code_parts = []
        
        code_parts.append("import ohos.base.*")
        code_parts.append("import ohos.component.*")
        code_parts.append("")
        
        ui_components = analysis.get("ui_components", [])
        if ui_components:
            code_parts.append("UI组件实现:")
            for comp in ui_components:
                component_type = comp.get("组件", "Component")
                code_parts.append(f"  // {comp.get('关键词')}: {component_type}")
        
        code_parts.append("")
        
        data_structures = analysis.get("data_structures", [])
        if data_structures:
            code_parts.append("数据结构:")
            for ds in data_structures:
                data_type = ds.get("数据结构", "DataModel")
                code_parts.append(f"  public class {data_type} {{")
                code_parts.append(f"    // TODO: 实现{ds.get('关键词')}相关字段")
                code_parts.append(f"  }}")
        
        code = "\n".join(code_parts)
        
        logger.info(f"代码生成完成，{len(code)} 字符")
        return code


class StdxConfigTool(Tool):
    stdx依赖配置工具。
    
    def __init__(self, stdx_zip_path: Path):
        super().__init__(name="stdx_config", description="配置stdx依赖包")
        self.stdx_zip_path = stdx_zip_path
    
    async def execute(self, project_root: Path) -> Dict[str, Any]:
        配置stdx依赖。
        
        Args:
            project_root: 项目根目录
            
        Returns:
            配置结果
        result = {
            "stdx_extracted": False,
            "cjpm_modified": False,
            "errors": []
        }
        
        if not project_root:
            result["errors"].append("项目根目录未设置")
            return result
        
        stdx_target = project_root / "cjnative" / "stdx"
        cjpm_path = project_root / "entry" / "cjpm.toml"
        
        try:
            # 1. 解压stdx包
            if not stdx_target.exists():
                logger.info(f"解压stdx包到: {stdx_target}")
                stdx_target.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(self.stdx_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(stdx_target)
                
                result["stdx_extracted"] = True
                logger.info("stdx解压完成")
            else:
                logger.info("stdx目录已存在，跳过解压")
                result["stdx_extracted"] = True
            
            # 2. 修改cjpm.toml
            if cjpm_path.exists():
                logger.info(f"修改cjpm配置: {cjpm_path}")
                
                content = cjpm_path.read_text(encoding="utf-8")
                
                # 检查是否已有配置
                if "stdx" not in content.lower():
                    # 添加bin-dependencies配置
                    if "[bin-dependencies]" in content:
                        # 添加到现有配置
                        content += '\n# stdx依赖'
                        content += 'path-option = ["${CANGJIE_PATH}/stdx"]\n'
                    else:
                        # 添加新的bin-dependencies配置
                        content += '\n\n[bin-dependencies]\n'
                        content += 'path-option = ["${CANGJIE_PATH}/stdx"]\n'
                    
                    cjpm_path.write_text(content, encoding="utf-8")
                    result["cjpm_modified"] = True
                    logger.info("cjpm配置完成")
                else:
                    logger.info("cjpm已经配置了stdx，跳过")
                    result["cjpm_modified"] = True
            else:
                result["errors"].append(f"cjpm.toml不存在: {cjpm_path}")
        
        except Exception as e:
            error_msg = f"stdx配置失败: {str(e)}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
        
        return result


class CangjieEngineerAgent(BaseAgent):
    仓颉工程师Agent。
    
    职责：
    1. 持有基础语法Skills和代码编写权限
    2. 负责stdx路径拼接逻辑
    3. 基于需求分析和知识检索生成代码
    
    输入：技术分析 + 知识检索结果
    输出：生成的代码 + stdx配置（写入黑板）
    
    def __init__(self, blackboard: GlobalState, llm_client=None, llm_model="Pro/zai-org/GLM-5"):
        system_prompt = 你是鸿蒙仓颉语言工程师，负责代码编写和依赖配置。

你的能力：
1. 基于需求分析和知识检索结果生成仓颉语言代码
2. 配置stdx扩展标准库的依赖路径
3. 确保代码符合仓颉语言语法规范
4. 处理ArkUI组件集成

工作流程：
1. 接收需求分析结果（UI组件、数据结构）
2. 接收知识检索结果（L1/L2/L3知识）
3. 基于Architect的设计生成仓颉代码
4. 配置stdx依赖包（解压、修改cjpm.toml）
5. 生成完整的代码框架

输出格式：
{
  "generated_code": "...",  # 生成的代码
  "stdx_config": {...},     # stdx配置结果
  "files_to_create": [...]  # 需要创建的文件列表
}

注意：
- 严格遵循仓颉语言语法规范
- 正确导入ArkUI组件
- stdx路径使用 ${CANGJIE_PATH} 变量
- 代码要结构清晰，易于维护
        
        super().__init__(
            name="CangjieEngineerAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        self.stdx_zip_path = PROJECT_ROOT / ".opencode" / "skills" / "harmonyos-stdx-dependency" / "cangjie-stdx-ohos-x86_64-1.1.0-beta.10.1.zip"
    
    async def register_tools(self) -> None:
        注册工具。
        
        await super().register_tools()
        self.add_tool(CodeGenerationTool())
        self.add_tool(StdxConfigTool(self.stdx_zip_path))
    
    async def process(self) -> Dict[str, Any]:
        执行代码生成和stdx配置。
        
        Returns:
            处理结果
        logger.info(f"[{self.name}] 开始代码生成...")
        
        # 从黑板获取数据
        technical_analysis = await self.blackboard.get("technical_analysis")
        knowledge_results = await self.blackboard.get("knowledge_results")
        project_root = await self.blackboard.get("project_root")
        
        if not technical_analysis:
            raise ValueError(f"[{self.name}] 缺少需求分析结果")
        
        results = {
            "generated_code": None,
            "stdx_config": None,
            "files_to_create": [],
        }
        
        # Step 1: 生成代码
        logger.info(f"[{self.name}] Step 1: 生成代码...")
        generated_code = await self.call_tool("code_generation", technical_analysis, knowledge_results)
        
        results["generated_code"] = generated_code
        
        # 也可以使用LLM增强代码生成
        if self.llm_client:
            try:
                llm_prompt = f"""
基于以下需求分析和知识检索结果，生成完整的仓颉语言代码：

需求分析:
{technical_analysis}

知识检索结果:
{knowledge_results}

要求：
1. 代码要符合仓颉语言语法规范
2. 包含完整的导入语句
3. 实现所需的UI组件和数据结构
4. 添加必要的注释
5. 代码要结构清晰
                """
                
                enhanced_code = await self.query_llm(llm_prompt, temperature=0.3)
                if enhanced_code and len(enhanced_code) > len(generated_code):
                    generated_code = enhanced_code
                    results["generated_code"] = generated_code
                    logger.info(f"[{self.name}] 使用LLM增强的代码")
            except Exception as e:
                logger.warning(f"[{self.name}] LLM代码增强失败: {e}")
        
        # 写入黑板
        await self.blackboard.update("generated_code", generated_code, agent_name=self.name)
        
        # Step 2: 配置stdx（如果有项目根目录）
        if project_root:
            logger.info(f"[{self.name}] Step 2: 配置stdx...")
            stdx_result = await self.call_tool("stdx_config", Path(project_root))
            results["stdx_config"] = stdx_result
            
            # 写入黑板
            await self.blackboard.update("dependencies", stdx_result, agent_name=self.name)
            
            if stdx_result.get("stdx_extracted") and stdx_result.get("cjpm_modified"):
                logger.info(f"[{self.name}] stdx配置成功")
            elif stdx_result.get("errors"):
                logger.warning(f"[{self.name}] stdx配置遇到问题: {stdx_result['errors']}")
        else:
            logger.info(f"[{self.name}] 跳过stdx配置（项目根目录未设置）")
            results["stdx_config"] = {"skipped": True, "reason": "项目根目录未设置"}
        
        # 确定需要创建的文件
        if generated_code:
            results["files_to_create"] = [
                "entry/src/main/ets/pages/Index.cj",
            ]
        
        logger.info(f"[{self.name}] 代码生成完成，{len(generated_code)} 字符")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
        }
