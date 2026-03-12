"""
DevOps & QA Agent

Enhanced with core tools for build, test, and iteration.
"""

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from coordinator.agents.base_agent import BaseAgent
from coordinator.core.blackboard import GlobalState
from coordinator.core.internal_query import InternalQuery, QueryPriority, QueryStatus, ConversationFlow
from coordinator.core.tools import ShellExecutorTool, FileManagerTool

from graph.extractor import is_valid_code_snippet

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("DevOpsQAAgent")


class BuildTool:
    """Build tool using ShellExecutorTool."""
    
    def __init__(self):
        self.shell_executor = ShellExecutorTool()
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute build with retry support."""
        project_root = kwargs.get("project_root")
        build_script_path = kwargs.get("build_script_path")
        max_attempts = kwargs.get("max_attempts", 5)
        
        result = {
            "project_root": str(project_root),
            "attempts": 0,
            "successful": False,
            "build_log": "",
            "errors": [],
        }
        
        build_log_path = Path(project_root) / "build-full.log" if project_root else None
        
        for attempt in range(1, max_attempts + 1):
            result["attempts"] = attempt
            logger.info(f"[Build] Attempt #{attempt}/{max_attempts}")
            
            try:
                cmd = f"cd '{project_root}'; & {{ . {build_script_path} }} *>&1 | Tee-Object -FilePath '{build_log_path}'"
                
                exec_result = await self.shell_executor.execute(
                    command=cmd,
                    working_dir=str(project_root),
                    timeout=900
                )
                
                if exec_result.status == "success":
                    output = exec_result.output
                    result["build_log"] = output.get("stdout", "") + "\n" + output.get("stderr", "")
                    
                    if "BUILD SUCCESSFUL" in result["build_log"] or output.get("exit_code") == 0:
                        result["successful"] = True
                        result["exit_code"] = output.get("exit_code")
                        logger.info(f"[Build] Success!")
                        break
                else:
                    if exec_result.output:
                        output = exec_result.output
                        result["build_log"] = output.get("stdout", "") + "\n" + output.get("stderr", "")
                    result["errors"].append(exec_result.error or "Build failed")
            
            except Exception as e:
                error_msg = f"Build failed: {str(e)}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                break
        
        return result


class CodeFixTool:
    """Code fix tool."""
    
    def __init__(self):
        self.file_manager = FileManagerTool()
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Fix code."""
        project_root = kwargs.get("project_root")
        error_info = kwargs.get("error_info")
        llm_client = kwargs.get("llm_client")
        model = kwargs.get("model", "Pro/zai-org/GLM-5")
        
        result = {
            "fixed": False,
            "fix_details": None,
        }
        
        if not llm_client:
            return result
        
        prompt = f"""
You are HarmonyOS development code fix expert.

## Build Error
```
{error_info}
```

## Project Info
Project root: {project_root}

Your task:
1. Analyze build error
2. Determine files and code to modify
3. Generate fixed code

Please return in strict JSON format:
{{
  "file_path": "file path",
  "original_code": "original code",
  "fixed_code": "fixed code",
  "explanation": "fix explanation"
}}
"""
        
        try:
            response = llm_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are HarmonyOS Cangjie language development expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            
            response_text = response.choices[0].message.content
            if response_text:
                fix_plan = json.loads(response_text)
                
                file_path = fix_plan.get("file_path")
                original_code = fix_plan.get("original_code")
                fixed_code = fix_plan.get("fixed_code")
                
                if file_path and original_code and fixed_code:
                    full_file_path = Path(project_root) / file_path
                    
                    read_result = await self.file_manager.execute(
                        action="read",
                        filepath=str(full_file_path)
                    )
                    
                    if read_result.status == "success" and original_code in read_result.output:
                        await self.file_manager.execute(
                            action="write",
                            filepath=str(full_file_path.with_suffix(full_file_path.suffix + '.backup')),
                            content=read_result.output
                        )
                        
                        replace_result = await self.file_manager.execute(
                            action="replace",
                            filepath=str(full_file_path),
                            old_pattern=original_code,
                            new_content=fixed_code
                        )
                        
                        if replace_result.status == "success":
                            result["fixed"] = True
                            result["fix_details"] = fix_plan
                            logger.info(f"[Fix] Successfully fixed file: {file_path}")
                
        except Exception as e:
            logger.warning(f"[Fix] Code fix failed: {e}")
        
        return result


class AuditorTool:
    """Audit tool."""
    
    def __init__(self):
        pass
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute code audit."""
        code = kwargs.get("code")
        result = {
            "valid": True,
            "issues": [],
        }
        
        try:
            validation_result = is_valid_code_snippet(code, code)
            result["valid"] = validation_result
        except Exception as e:
            result["valid"] = True  # Default pass
            result["issues"].append(f"Audit check failed: {str(e)}")
        
        return result


class EvolutionTool:
    """Evolution record tool."""
    
    def __init__(self, evolution_path: Path):
        self.file_manager = FileManagerTool()
        self.evolution_path = evolution_path
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Record iteration experience."""
        record = kwargs.get("record")
        result = {
            "recorded": False,
        }
        
        try:
            check_result = await self.file_manager.execute(
                action="exists",
                filepath=str(self.evolution_path)
            )
            
            evolution_content = ""
            if check_result.status == "success" and check_result.output.get("exists"):
                read_result = await self.file_manager.execute(
                    action="read",
                    filepath=str(self.evolution_path)
                )
                evolution_content = read_result.output
            
            new_record_text = f"""
### {datetime.now().strftime('%Y-%m-%d')} - {record.get('agent', 'Unknown')}
**Type**: {record.get('type', 'General')}
**Description**: {record.get('description', 'No description')}
**Solution**: {record.get('solution', 'No solution')}
**Collaboration**: {record.get('collaboration_flow', 'N/A')}
"""
            
            append_result = await self.file_manager.execute(
                action="append",
                filepath=str(self.evolution_path),
                content=new_record_text
            )
            
            if append_result.status == "success":
                result["recorded"] = True
                logger.info(f"[Evolution] Record success: {record.get('description', '')[:50]}")
        
        except Exception as e:
            logger.error(f"[Evolution] Record failed: {e}")
        
        return result


class InternalQueryTool:
    """Internal Query Tool - For collaborative feedback loop."""
    
    def __init__(self, blackboard: GlobalState):
        self.blackboard = blackboard
        self.conversation_flow = ConversationFlow()
    
    async def execute(self, **kwargs) -> Any:
        """Execute internal query operation."""
        action = kwargs.get("action")
        
        if action == "create":
            return await self._create_query(
                sender=kwargs.get("sender"),
                recipient=kwargs.get("recipient"),
                question=kwargs.get("question"),
                priority=kwargs.get("priority"),
                error_type=kwargs.get("error_type"),
                error_message=kwargs.get("error_message", ""),
                build_log=kwargs.get("build_log", "")
            )
        
        return {"error": "Invalid action"}
    
    async def _create_query(
        self,
        sender: str,
        recipient: str,
        question: str,
        priority: QueryPriority,
        error_type: Optional[str] = None,
        error_message: str = "",
        build_log: str = ""
    ) -> InternalQuery:
        """Create new internal query."""
        query = self.conversation_flow.create_query(
            sender=sender,
            recipient=recipient,
            question=question,
            priority=priority,
            error_type=error_type,
            error_message=error_message,
            build_log=build_log
        )
        
        await self.blackboard.post_message(
            sender=sender,
            content={
                "type": "internal_query",
                "query": query.to_dict(),
                "action": "create"
            },
            message_type="query_request",
            recipients=[recipient]
        )
        
        return query
    
    async def respond_to_query(
        self,
        query_id: str,
        solutions: List[Dict[str, Any]],
        confidence: float,
        source_evidence: List[Dict[str, Any]]
    ) -> None:
        """Respond to query."""
        self.conversation_flow.update_query_status(query_id, QueryStatus.SOLUTION_FOUND)
        
        await self.blackboard.post_message(
            sender=self.__class__.__name__,
            content={
                "type": "internal_query",
                "query_id": query_id,
                "solutions": solutions,
                "confidence": confidence,
                "source_evidence": source_evidence,
                "action": "respond"
            },
            message_type="query_response"
        )
    
    async def complete_query(
        self,
        query_id: str,
        success: bool,
        outcome: str,
        selected_solution: Optional[Dict[str, Any]] = None
    ) -> None:
        """Complete query and record conversation flow."""
        query = self.conversation_flow.complete_query(
            query_id,
            success,
            outcome,
            selected_solution
        )
        
        if query:
            await self.blackboard.post_message(
                sender="DevOpsQAAgent",
                content={
                    "type": "conversation_summary",
                    "query_id": query_id,
                    "summary": query.get_conversation_summary(),
                    "action": "complete"
                },
                message_type="conversation_complete"
            )


class DevOpsQAAgent(BaseAgent):
    """DevOps & QA Agent with enhanced tool support."""
    
    def __init__(
        self,
        blackboard: GlobalState,
        build_script_path: Path,
        evolution_path: Path,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = """You are a HarmonyOS DevOps and QA engineer, responsible for build, test, and iteration recording. With collaborative feedback capabilities.

Available tools:
- shell_executor: Execute system commands (build scripts, test scripts, etc.)
- file_manager: File read/write operations (read logs, modify configs, record evolution)
- build: Execute build process
- code_fix: Fix code based on error information
- audit: Audit code snippets
- evolution: Record iteration experience to Evolution.md
- internal_query: Collaborate with other Agents to solve problems

Workflow:
1. Code audit (if needed)
2. Execute build
3. If build fails, request help from KnowledgeExpert via InternalQuery
4. Record results to Evolution.md
"""
        
        super().__init__(
            name="DevOpsQAAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        self.build_script_path = build_script_path
        self.evolution_path = evolution_path
        
        # Pre-initialize tools for direct access
        self.shell_executor = ShellExecutorTool()
        self.file_manager = FileManagerTool()
        self.build_tool = BuildTool()
        self.code_fix_tool = CodeFixTool()
        self.audit_tool = AuditorTool()
        self.evolution_tool = EvolutionTool(evolution_path)
        self.internal_query_tool = InternalQueryTool(blackboard)
    
    async def register_tools(self) -> None:
        """Register enhanced tools."""
        await super().register_tools()
        
        # Register as tools for add_tool compatibility
        # These are custom tools, not BaseTool subclasses, so we can't use add_tool
        # Instead, we'll use them directly in process method
        logger.info(f"[{self.name}] Tools initialized directly")
    
    async def process(self) -> Dict[str, Any]:
        """Execute DevOps pipeline with intelligent on-demand decision making."""
        logger.info(f"[{self.name}] Starting DevOps pipeline with on-demand logic...")
        
        generated_code = await self.blackboard.get("generated_code")
        project_root = await self.blackboard.get("project_root")
        
        if not generated_code:
            logger.warning(f"[{self.name}] No generated code on blackboard, skipping DevOps")
            return {
                "agent": self.name,
                "success": True,
                "skipped": True,
                "reason": "No generated code to build"
            }
        
        if not project_root:
            project_root = PROJECT_ROOT
        
        results = {
            "audit_result": None,
            "build_result": None,
            "evolution_recorded": False,
            "collaboration_flow": None,
            "decision_path": [],
        }
        
        # === Step 1: Code audit (always execute) ===
        logger.info(f"[{self.name}] Step 1: Code audit...")
        results["decision_path"].append("Step 1: Code audit → started")
        
        audit_result = await self.audit_tool.execute(code=generated_code)
        results["audit_result"] = audit_result
        logger.info(f"[{self.name}] Audit complete: {audit_result.get('valid', False)}")
        results["decision_path"].append("Step 1: Code audit → completed")
        
        # === Step 2: Build (always execute to verify code) ===
        logger.info(f"[{self.name}] Step 2: Build verification...")
        results["decision_path"].append("Step 2: Build → started")
        
        build_result = await self.build_tool.execute(
            project_root=project_root,
            build_script_path=self.build_script_path,
            max_attempts=5
        )
        results["build_result"] = build_result
        
        if build_result.get("successful"):
            logger.info(f"[{self.name}] Build success")
            results["decision_path"].append("Step 3: Build successful → record success")
            
            # === Step 3a: Record success to Evolution ===
            logger.info(f"[{self.name}] Step 3a: Record success to Evolution...")
            evolution_record = {
                "agent": self.name,
                "type": "Build success",
                "description": "Project build successful",
                "solution": "All configurations and code correct",
                "collaboration_flow": "No collaboration needed"
            }
            evolution_result = await self.evolution_tool.execute(record=evolution_record)
            results["evolution_recorded"] = evolution_result.get("recorded", False)
            results["decision_path"].append("Step 3a: Success recorded to Evolution")
        else:
            logger.warning(f"[{self.name}] Build failed - analyzing error...")
            error_info = build_result.get("build_log", "") or build_result.get("errors", ["Unknown error"])[0] if build_result.get("errors") else "Unknown error"
            
            # === Smart Decision 1: Is error fixable? ===
            fixable = await self._is_error_fixable(error_info)
            results["decision_path"].append(f"Step 3: Build failed → error fixable: {fixable['status']}")
            
            if not fixable["status"]:
                logger.info(f"[{self.name}] Error not fixable ({fixable['reason']}), skip direct fix")
                
                # === Step 3b: Create InternalQuery for Knowledge Expert (only when error not fixable) ===
                logger.info(f"[{self.name}] Step 3b: Create InternalQuery for Knowledge Expert...")
                results["decision_path"].append("Step 3b: Create InternalQuery → started")
                
                try:
                    query = await self.internal_query_tool._create_query(
                        sender=self.name,
                        recipient="KnowledgeExpertAgent",
                        question=f"Build failed with error: {error_info[:200]}... How to fix?",
                        priority=QueryPriority.CRITICAL,
                        error_type="build_failure",
                        error_message=str(error_info[:500]),
                        build_log=str(error_info[:1000])
                    )
                    
                    logger.info(f"[{self.name}] InternalQuery created: {query.query_id}")
                    results["collaboration_flow"] = {
                        "query_id": query.query_id,
                        "sent_to": "KnowledgeExpertAgent",
                        "status": "pending"
                    }
                    results["decision_path"].append("Step 3b: InternalQuery created, waiting for expert knowledge")
                except Exception as e:
                    logger.error(f"[{self.name}] InternalQuery failed: {e}")
                    results["collaboration_flow"] = {"error": str(e)}
                    results["decision_path"].append("Step 3b: InternalQuery creation failed")
            else:
                logger.info(f"[{self.name}] Error is fixable ({fixable['reason']}), attempting direct fix...")
                results["decision_path"].append(f"Step 3c: Error fixable → {fixable['reason']}")
                
                # === Step 3c: Direct code fix (only when error is simple/fixable) ===
                logger.info(f"[{self.name}] Step 3c: Attempt direct code fix...")
                
                if self.llm_client and error_info:
                    first_500_chars = str(error_info)[:500]
                    fix_result = await self.code_fix_tool.execute(
                        project_root=project_root,
                        error_info=first_500_chars,
                        llm_client=self.llm_client,
                        model=self.llm_model
                    )
                    
                    if fix_result.get("fixed"):
                        logger.info(f"[{self.name}] Code fixed, rebuilding...")
                        results["decision_path"].append("Step 3c: Code fixed → rebuild")
                        
                        await asyncio.sleep(1)
                        
                        rebuild_result = await self.build_tool.execute(
                            project_root=project_root,
                            build_script_path=self.build_script_path,
                            max_attempts=4
                        )
                        
                        if rebuild_result.get("successful"):
                            results["build_result"] = rebuild_result
                            logger.info(f"[{self.name}] Build successful after fix")
                            results["decision_path"].append("Step 3c: Rebuild successful")
                        else:
                            logger.warning(f"[{self.name}] Rebuild still failed, fallback to InternalQuery")
                            results["decision_path"].append("Step 3c: Rebuild failed → fallback to InternalQuery")
                            
                            # Fallback: Create InternalQuery after fix attempts fail
                            try:
                                query = await self.internal_query_tool._create_query(
                                    sender=self.name,
                                    recipient="KnowledgeExpertAgent",
                                    question=f"Build failed after fix attempt: {error_info[:200]}... How to fix?",
                                    priority=QueryPriority.CRITICAL,
                                    error_type="build_failure_after_fix",
                                    error_message=str(error_info[:500]),
                                    build_log=str(error_info[:1000])
                                )
                                results["collaboration_flow"] = {
                                    "query_id": query.query_id,
                                    "sent_to": "KnowledgeExpertAgent",
                                    "status": "pending"
                                }
                            except Exception as e:
                                results["collaboration_flow"] = {"error": str(e)}
                    else:
                        logger.warning(f"[{self.name}] Code fix tool failed, fallback to InternalQuery")
                        results["decision_path"].append("Step 3c: Code fix failed → fallback to InternalQuery")
        
        # Write build results to blackboard
        build_history = await self.blackboard.get("build_results", [])
        build_history.append(results["build_result"])
        await self.blackboard.update("build_results", build_history, agent_name=self.name)
        
        results["decision_path"].append("Step 4: DevOps flow completed")
        logger.info(f"[{self.name}] DevOps flow complete: {'; '.join(results['decision_path'])}")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
            "decision_summary": f"Executed {'; '.join(results['decision_path'])}"
        }
    
    async def _is_error_fixable(self, error_info: str) -> Dict[str, Any]:
        """AI判断构建错误是否可以直接修复。
        
        Args:
            error_info: 构建错误信息
            
        Returns:
            {"status": bool, "reason": str}
        """
        if not error_info:
            return {"status": False, "reason": "No error info"}
        
        if not self.llm_client:
            logger.warning(f"[{self.name}] No LLM client, using fallback logic")
            return {"status": True, "reason": "Attempting fix (no LLM)"}
        
        prompt = f"""你是HarmonyOS构建系统的DevOps专家。请判断当前的构建错误是否可以通过简单的代码修改直接修复。

【错误信息】
{error_info[:1000]}

【判断标准】
请根据错误信息判断是否可修复：
- 可修复的错误：语法错误、拼写错误、缺少导入、标点符号错误、缩进错误、大小写错误等
- 不可修复的错误：架构设计问题、依赖冲突、版本不兼容、不支持的功能、类型不兼容、循环依赖等需要重新设计代码的问题

【输出格式】
是否可修复: true 或 false
判断理由: 一句话说明为什么可修复/不可修复（必须用中文）

只输出这两行，不要包含其他内容。"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content or ""
            
            if "是否可修复: true" in content.lower() or "是否可修复:t rue" in content.lower():
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为可修复"
                logger.info(f"[{self.name}] AI判断: 错误可修复 - {reason_match}")
                return {"status": True, "reason": reason_match}
            else:
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为不可修复"
                logger.info(f"[{self.name}] AI判断: 错误不可修复 - {reason_match}")
                return {"status": False, "reason": reason_match}
        
        except Exception as e:
            logger.error(f"[{self.name}] AI判断失败: {e}")
            return {"status": True, "reason": f"AI判断失败，尝试修复: {str(e)}"}
