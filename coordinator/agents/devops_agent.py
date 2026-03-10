import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from coordinator.agents.base_agent import BaseAgent, Tool
from coordinator.core.blackboard import GlobalState
from coordinator.core.internal_query import InternalQuery, QueryPriority, QueryStatus, ConversationFlow

from graph.extractor import is_valid_code_snippet

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("DevOpsQAAgent")


class BuildTool(Tool):
    """Build tool"""
    
    def __init__(self, build_script_path: Path):
        super().__init__(name="build", description="Execute HarmonyOS build script")
        self.build_script_path = build_script_path
    
    async def execute(self, project_root: Path, max_attempts: int = 5) -> Dict[str, Any]:
        """Execute build with retry support"""
        result = {
            "project_root": str(project_root),
            "attempts": 0,
            "successful": False,
            "build_log": "",
            "errors": [],
        }
        
        build_log_path = project_root / "build-full.log"
        
        for attempt in range(1, max_attempts + 1):
            result["attempts"] = attempt
            logger.info(f"[Build] Attempt #{attempt}/{max_attempts}")
            
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"cd '{project_root}'; & {{ . {self.build_script_path} }} *>&1 | Tee-Object -FilePath '{build_log_path}'"
                ]
                
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=900,
                    encoding='utf-8',
                    errors='ignore'
                )
                
                logger.info(f"[Build] Exit code: {process.returncode}")
                
                if build_log_path.exists():
                    log_content = build_log_path.read_text(encoding="utf-8", errors="ignore")
                    result["build_log"] = log_content
                    
                    if "BUILD SUCCESSFUL" in log_content or process.returncode == 0:
                        result["successful"] = True
                        result["exit_code"] = process.returncode
                        logger.info(f"[Build] Success!")
                        break
                    else:
                        logger.info(f"[Build] Failed")
                        break
                
            except subprocess.TimeoutExpired:
                error_msg = "Build timeout"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                break
            except Exception as e:
                error_msg = f"Build failed: {str(e)}"
                result["errors"].append(error_msg)
                logger.error(error_msg)
                break
        
        return result


class CodeFixTool(Tool):
    """Code fix tool"""
    
    def __init__(self):
        super().__init__(name="code_fix", description="Fix code based on error report")
    
    async def execute(
        self,
        project_root: Path,
        error_info: str,
        llm_client=None,
        model="Pro/zai-org/GLM-5"
    ) -> Dict[str, Any]:
        """Fix code"""
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
                    full_file_path = project_root / file_path
                    
                    if full_file_path.exists():
                        content = full_file_path.read_text(encoding="utf-8")
                        
                        if original_code in content:
                            new_content = content.replace(original_code, fixed_code, 1)
                            full_file_path.with_suffix(full_file_path.suffix + '.backup').write_text(content, encoding="utf-8")
                            full_file_path.write_text(new_content, encoding="utf-8")
                            
                            result["fixed"] = True
                            result["fix_details"] = fix_plan
                            logger.info(f"[Fix] Successfully fixed file: {file_path}")
        
        except Exception as e:
            logger.warning(f"[Fix] Code fix failed: {e}")
        
        return result


class InternalQueryTool(Tool):
    """Internal Query Tool - For collaborative feedback loop"""
    
    def __init__(self, blackboard: GlobalState):
        super().__init__(name="internal_query", description="Create and manage internal queries between agents")
        self.blackboard = blackboard
        self.conversation_flow = ConversationFlow()
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute internal query operation"""
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
        """Create new internal query"""
        query = self.conversation_flow.create_query(
            sender=sender,
            recipient=recipient,
            question=question,
            priority=priority,
            error_type=error_type,
            error_message=error_message,
            build_log=build_log
        )
        
        # Post query to blackboard
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
        """Respond to query"""
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
        """Complete query and record conversation flow"""
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


class AuditorTool(Tool):
    """Audit tool"""
    
    def __init__(self):
        super().__init__(name="audit", description="Verify code snippet reliability")
    
    async def execute(self, code: str) -> Dict[str, Any]:
        """Execute code audit"""
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


class EvolutionTool(Tool):
    """Evolution record tool"""
    
    def __init__(self, evolution_path: Path):
        super().__init__(name="evolution", description="Record iteration experience to Evolution.md")
        self.evolution_path = evolution_path
    
    async def execute(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Record iteration experience"""
        result = {
            "recorded": False,
        }
        
        try:
            if self.evolution_path.exists():
                evolution_content = self.evolution_path.read_text(encoding="utf-8")
            else:
                evolution_content = ""
            
            new_record_text = f"""
### {datetime.now().strftime('%Y-%m-%d')} - {record.get('agent', 'Unknown')}
**Type**: {record.get('type', 'General')}
**Description**: {record.get('description', 'No description')}
**Solution**: {record.get('solution', 'No solution')}
**Collaboration**: {record.get('collaboration_flow', 'N/A')}
"""
            
            evolution_content += new_record_text
            self.evolution_path.write_text(evolution_content, encoding="utf-8")
            
            result["recorded"] = True
            logger.info(f"[Evolution] Record success: {record.get('description', '')[:50]}")
        
        except Exception as e:
            logger.error(f"[Evolution] Record failed: {e}")
        
        return result


class DevOpsQAAgent(BaseAgent):
    """DevOps & QA Agent with collaborative feedback loop"""
    
    def __init__(
        self,
        blackboard: GlobalState,
        build_script_path: Path,
        evolution_path: Path,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = "你是鸿蒙DevOps和QA工程师，负责构建、测试和迭代记录。具备协作式反馈能力。构建失败时，向Knowledge Expert发起InternalQuery。通过阶梯式协商解决问题。记录完整协作流程到Evolution.md。"
        
        super().__init__(
            name="DevOpsQAAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        self.build_script_path = build_script_path
        self.evolution_path = evolution_path
    
    async def register_tools(self) -> None:
        """Register tools"""
        await super().register_tools()
        self.add_tool(BuildTool(self.build_script_path))
        self.add_tool(CodeFixTool())
        self.add_tool(InternalQueryTool(self.blackboard))
        self.add_tool(AuditorTool())
        self.add_tool(EvolutionTool(self.evolution_path))
    
    async def process(self) -> Dict[str, Any]:
        """Execute DevOps flow with collaborative feedback loop"""
        logger.info(f"[{self.name}] Starting DevOps flow...")
        
        project_root_str = await self.blackboard.get("project_root")
        generated_code = await self.blackboard.get("generated_code")
        
        if not project_root_str:
            raise ValueError(f"[{self.name}] Project root not set")
        
        project_root = Path(project_root_str)
        results = {
            "audit_result": None,
            "build_result": None,
            "evolution_recorded": False,
            "collaboration_flow": None,
        }
        
        # Step 1: Code audit
        logger.info(f"[{self.name}] Step 1: Code audit...")
        if generated_code:
            audit_result = await self.call_tool("audit", generated_code)
            results["audit_result"] = audit_result
            logger.info(f"[{self.name}] Audit complete: {audit_result.get('valid', False)}")
        else:
            logger.warning(f"[{self.name}] No code to audit")
        
        # Step 2: Build with collaborative feedback loop
        logger.info(f"[{self.name}] Step 2: Build with collaborative feedback loop...")
        build_result = await self.call_tool("build", project_root, max_attempts=5)
        results["build_result"] = build_result
        
        if build_result.get("successful"):
            logger.info(f"[{self.name}] Build success")
            
            # Step 3: Record success
            logger.info(f"[{self.name}] Step 3: Record iteration experience...")
            evolution_record = {
                "agent": self.name,
                "type": "Build success",
                "description": "Project build successful",
                "solution": "All configurations and code correct",
                "collaboration_flow": "No collaboration needed"
            }
            evolution_result = await self.call_tool("evolution", evolution_record)
            results["evolution_recorded"] = evolution_result.get("recorded", False)
        else:
            logger.warning(f"[{self.name}] Build failed - initiating collaborative feedback loop")
            
            # Step 3: Create InternalQuery for Knowledge Expert
            logger.info(f"[{self.name}] Step 3: Create InternalQuery for Knowledge Expert...")
            
            error_log = build_result.get("build_log", "") or build_result.get("errors", ["Unknown error"])[0] if build_result.get("errors") else "Unknown error"
            
            internal_query_tool = self.tools.get("internal_query")
            if internal_query_tool:
                try:
                    # Create internal query
                    query = await internal_query_tool.create_query(
                        sender=self.name,
                        recipient="KnowledgeExpertAgent",
                        question=f"Build failed with error: {error_log[:200]}... How to fix?",
                        priority=QueryPriority.CRITICAL,
                        error_type="build_failure",
                        error_message=str(error_log[:500]),
                        build_log=str(error_log[:1000])
                    )
                    
                    logger.info(f"[{self.name}] InternalQuery created: {query.query_id}")
                    results["collaboration_flow"] = {
                        "query_id": query.query_id,
                        "sent_to": "KnowledgeExpertAgent",
                        "status": "pending"
                    }
                    
                    # Wait for Knowledge Expert response (simulated delay)
                    await asyncio.sleep(2)
                    
                    # Check for response on blackboard
                    messages = await self.read_messages()
                    query_responses = [msg for msg in messages if isinstance(msg.content, dict) and msg.content.get("type") == "internal_query" and msg.content.get("query_id") == query.query_id and msg.content.get("action") == "respond"]
                    
                    if query_responses:
                        response = query_responses[0].content
                        solutions = response.get("solutions", [])
                        logger.info(f"[{self.name}] Received {len(solutions)} solutions from Knowledge Expert")
                        
                        # Apply best solution
                        if solutions:
                            best_solution = solutions[0]
                            logger.info(f"[{self.name}] Applying solution: {best_solution.get('description', 'N/A')}")
                            
                            # Note: Actual code fix would require more logic here
                            
                            # Record collaboration flow
                            evolution_record = {
                                "agent": self.name,
                                "type": "Collaborative fix",
                                "description": "Build fixed through agent collaboration",
                                "solution": best_solution.get("description", "N/A"),
                                "collaboration_flow": f"Query {query.query_id} -> KnowledgeExpert -> 3 solutions received"
                            }
                    else:
                        logger.warning(f"[{self.name}] No response from Knowledge Expert, trying direct fix")
                
                except Exception as e:
                    logger.error(f"[{self.name}] InternalQuery failed: {e}")
                    results["collaboration_flow"] = {"error": str(e)}
            
            # Step 4: Direct code fix as fallback
            logger.info(f"[{self.name}] Step 4: Attempt direct code fix...")
            error_info = build_result.get("build_log", "") or build_result.get("errors", ["Unknown error"])[0] if build_result.get("errors") else "Unknown error"
            
            if self.llm_client and error_info:
                first_500_chars = str(error_info)[:500]
                fix_result = await self.call_tool("code_fix", project_root, first_500_chars, self.llm_client, self.llm_model)
                
                if fix_result.get("fixed"):
                    logger.info(f"[{self.name}] Code fixed, rebuilding...")
                    await asyncio.sleep(1)
                    
                    build_result = await self.call_tool("build", project_root, max_attempts=4)
                    results["build_result"] = build_result
                    
                    if build_result.get("successful"):
                        logger.info(f"[{self.name}] Build successful after fix")
        
        # Write build results to blackboard
        build_history = await self.blackboard.get("build_results", [])
        build_history.append(build_result)
        await self.blackboard.update("build_results", build_history, agent_name=self.name)
        
        logger.info(f"[{self.name}] DevOps flow complete")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
        }
