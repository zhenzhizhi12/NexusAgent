"""
Cangjie Engineer Agent

Responsible for code generation and stdx dependency configuration.
Holds Cangjie language basic skills and code writing permissions.
"""

import logging
from pathlib import Path
from typing import Any, Dict

from coordinator.agents.base_agent import BaseAgent
from coordinator.core.blackboard import GlobalState
from coordinator.core.tool import BaseTool, ToolExecutionResult
from coordinator.core.tools import FileManagerTool

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("CangjieEngineerAgent")


class CodeGenerationTool(BaseTool):
    """Code generation tool for Cangjie language."""
    
    def __init__(self):
        super().__init__(
            name="code_generation",
            description="Generate Cangjie code based on requirement analysis and knowledge retrieval",
        )
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute code generation."""
        analysis = kwargs.get("analysis", {})
        knowledge = kwargs.get("knowledge", {})
        
        code_parts = []
        code_parts.append("import ohos.base.*")
        code_parts.append("import ohos.component.*")
        code_parts.append("")
        
        ui_components = analysis.get("ui_components", [])
        if ui_components:
            code_parts.append("UI Components:")
            for comp in ui_components:
                component_type = comp.get("component", "Component")
                code_parts.append(f"  // {comp.get('keyword')}: {component_type}")
        
        code_parts.append("")
        
        data_structures = analysis.get("data_structures", [])
        if data_structures:
            code_parts.append("Data Structures:")
            for ds in data_structures:
                data_type = ds.get("data_structure", "DataModel")
                code_parts.append(f"  public class {data_type} {{")
                code_parts.append(f"    // TODO: Implement fields for {ds.get('keyword')}")
                code_parts.append(f"  }}")
        
        code = "\n".join(code_parts)
        logger.info(f"Code generation completed, {len(code)} characters")
        
        return ToolExecutionResult(
            status="success",
            output=code,
            metadata={
                "code_length": len(code),
                "ui_components": len(ui_components),
                "data_structures": len(data_structures)
            }
        )


class StdxConfigTool(BaseTool):
    """Stdx dependency configuration tool."""
    
    def __init__(self, stdx_zip_path: Path):
        super().__init__(
            name="stdx_config",
            description="Configure stdx dependency package"
        )
        self.stdx_zip_path = stdx_zip_path
        self.file_manager = FileManagerTool()
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Configure stdx dependency."""
        project_root = kwargs.get("project_root")
        
        if not project_root:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="Project root not set"
            )
        
        project_path = Path(project_root)
        result = {
            "stdx_extracted": False,
            "cjpm_modified": False,
            "errors": []
        }
        
        stdx_target = project_path / "cjnative" / "stdx"
        cjpm_path = project_path / "entry" / "cjpm.toml"
        
        try:
            # Extract stdx package
            if not stdx_target.exists():
                import zipfile
                logger.info(f"Extracting stdx to: {stdx_target}")
                stdx_target.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(self.stdx_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(stdx_target)
                
                result["stdx_extracted"] = True
                logger.info("Stdx extraction completed")
            else:
                logger.info("Stdx directory exists, skipping extraction")
                result["stdx_extracted"] = True
            
            # Modify cjpm.toml
            if cjpm_path.exists():
                read_result = await self.file_manager.execute(
                    action="read",
                    filepath=str(cjpm_path)
                )
                
                if read_result.status == "success":
                    content = read_result.output
                    
                    # Check if stdx already configured
                    if "stdx" not in content.lower():
                        # Add bin-dependencies configuration
                        if "[bin-dependencies]" in content:
                            content += '\n# stdx dependency\npath-option = ["${CANGJIE_PATH}/stdx"]\n'
                        else:
                            content += '\n\n[bin-dependencies]\npath-option = ["${CANGJIE_PATH}/stdx"]\n'
                        
                        write_result = await self.file_manager.execute(
                            action="write",
                            filepath=str(cjpm_path),
                            content=content
                        )
                        
                        if write_result.status == "success":
                            result["cjpm_modified"] = True
                            logger.info("Cjpm configuration completed")
                    else:
                        logger.info("Cjpm already configured with stdx")
                        result["cjpm_modified"] = True
            else:
                result["errors"].append(f"cjpm.toml not found: {cjpm_path}")
        
        except Exception as e:
            error_msg = f"Stdx configuration failed: {str(e)}"
            result["errors"].append(error_msg)
            logger.error(error_msg)
        
        return ToolExecutionResult(
            status="success" if not result["errors"] else "error",
            output=result,
            metadata=result
        )


class CangjieEngineerAgent(BaseAgent):
    """Cangjie Engineer Agent.
    
    Responsibilities:
    - Hold basic language skills and code writing permissions
    - Responsible for stdx path configuration logic
    - Generate Cangjie code based on requirement analysis and knowledge retrieval
    - Configure stdx dependency packages
    
    Input: Technical analysis + knowledge retrieval results
    Output: Generated code + stdx configuration (written to blackboard)
    """
    
    def __init__(
        self,
        blackboard: GlobalState,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = """You are a HarmonyOS Cangjie language engineer, responsible for code writing and dependency configuration.

Your capabilities:
1. Generate Cangjie language code based on requirement analysis and knowledge retrieval
2. Configure stdx extension standard library dependency paths
3. Ensure code complies with Cangjie language syntax specifications
4. Handle ArkUI component integration

Workflow:
1. Receive requirement analysis results (UI components, data structures)
2. Receive knowledge retrieval results (L1/L2/L3 knowledge)
3. Generate Cangjie code based on Architect's design
4. Configure stdx dependency package (extract, modify cjpm.toml)
5. Generate complete code framework

Output format:
{
  "generated_code": "...",  # Generated code
  "stdx_config": {...},     # stdx configuration result
  "files_to_create": [...]  # Files to be created
}

Notes:
- Strictly follow Cangjie language syntax specifications
- Correctly import ArkUI components
- Use ${CANGJIE_PATH} variable for stdx paths
- Code should be clearly structured and easy to maintain
"""
        
        super().__init__(
            name="CangjieEngineerAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        self.stdx_zip_path = PROJECT_ROOT / ".opencode" / "skills" / "harmonyos-stdx-dependency" / "cangjie-stdx-ohos-x86_64-1.1.0-beta.10.1.zip"
        
        # Pre-initialize tools
        self.code_generation_tool = CodeGenerationTool()
        self.stdx_config_tool = StdxConfigTool(self.stdx_zip_path)
    
    async def register_tools(self) -> None:
        """Register tools."""
        await super().register_tools()
        logger.info(f"[{self.name}] Tools registered")
    
    async def process(self) -> Dict[str, Any]:
        """Execute code generation and stdx configuration."""
        logger.info(f"[{self.name}] Starting code generation...")
        
        # Get data from blackboard
        technical_analysis = await self.blackboard.get("technical_analysis")
        knowledge_results = await self.blackboard.get("knowledge_results")
        project_root = await self.blackboard.get("project_root")
        
        if not technical_analysis:
            raise ValueError(f"[{self.name}] Missing requirement analysis results")
        
        results = {
            "generated_code": None,
            "stdx_config": None,
            "files_to_create": [],
        }
        
        # Step 1: Generate code
        logger.info(f"[{self.name}] Step 1: Generating code...")
        code_result = await self.code_generation_tool.execute(
            analysis=technical_analysis,
            knowledge=knowledge_results
        )
        
        if code_result.status == "success":
            generated_code = code_result.output
            results["generated_code"] = generated_code
            
            # Write to blackboard
            await self.blackboard.update("generated_code", generated_code, agent_name=self.name)
            logger.info(f"[{self.name}] Code generation completed, {len(generated_code)} characters")
        else:
            logger.error(f"[{self.name}] Code generation failed: {code_result.error}")
            generated_code = ""
        
        # Step 2: Configure stdx (if project root is set)
        if project_root:
            logger.info(f"[{self.name}] Step 2: Configuring stdx...")
            stdx_result = await self.stdx_config_tool.execute(
                project_root=project_root
            )
            results["stdx_config"] = stdx_result.output
            
            # Write to blackboard
            await self.blackboard.update("dependencies", stdx_result.output, agent_name=self.name)
            
            if stdx_result.status == "success":
                output = stdx_result.output
                if output and output.get("stdx_extracted") and output.get("cjpm_modified"):
                    logger.info(f"[{self.name}] Stdx configuration successful")
            else:
                logger.warning(f"[{self.name}] Stdx configuration issues: {stdx_result.error}")
        else:
            logger.info(f"[{self.name}] Skipping stdx configuration (project root not set)")
            results["stdx_config"] = {"skipped": True, "reason": "Project root not set"}
        
        # Determine files to create
        if generated_code:
            results["files_to_create"] = [
                "entry/src/main/ets/pages/Index.cj",
            ]
        
        logger.info(f"[{self.name}] Code generation completed")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
        }
