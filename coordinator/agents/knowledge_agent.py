"""
Knowledge Expert Agent

Responsible for knowledge retrieval and reasoning.
Supports global architecture problems, L1/L3 knowledge search, and InternalQuery handling.
"""

import datetime
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from coordinator.agents.base_agent import BaseAgent
from coordinator.agents.intent_router import IntentRouter, EvidenceExtractor, SearchContext
from coordinator.core.blackboard import GlobalState
from coordinator.core.internal_query import InternalQuery, QueryPriority, QueryStatus
from coordinator.core.tool import BaseTool, ToolExecutionResult

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("KnowledgeAgent")


class EvolutionSearchTool(BaseTool):
    """Search Evolution.md for similar problems."""
    
    def __init__(self, evolution_path: Path):
        super().__init__(
            name="evolution_search",
            description="Search Evolution.md for similar problems"
        )
        self.evolution_path = evolution_path
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Search Evolution.md for similar errors."""
        error_keywords = kwargs.get("error_keywords", [])
        matched_solutions = []
        
        if not self.evolution_path.exists():
            logger.warning(f"Evolution.md not found: {self.evolution_path}")
            return ToolExecutionResult(
                status="error",
                output=[],
                error="Evolution.md not found"
            )
        
        try:
            content = self.evolution_path.read_text(encoding="utf-8", errors="ignore")
            logger.info(f"Read Evolution.md ({len(content)} bytes)")
            
            sections = re.split(r'###\s+', content)
            
            for section in sections:
                if not section:
                    continue
                
                match_score = sum(section.lower().count(kw.lower()) for kw in error_keywords)
                
                if match_score > 0:
                    lines = section.split('\n')
                    solution_text = '\n'.join(lines[3:])
                    
                    matched_solutions.append({
                        "source": "Evolution.md",
                        "match_score": match_score,
                        "solution_text": solution_text[:500],
                        "full_match": section,
                    })
            
            matched_solutions.sort(key=lambda x: x["match_score"], reverse=True)
            logger.info(f"Found {len(matched_solutions)} solutions in Evolution.md")
        
        except Exception as e:
            logger.error(f"Failed to search Evolution.md: {e}")
        
        return ToolExecutionResult(
            status="success",
            output=matched_solutions,
            metadata={"matched_count": len(matched_solutions)}
        )


class ThrowsRelationSearchTool(BaseTool):
    """Search THROWS relations in graph."""
    
    def __init__(self, search_engine):
        super().__init__(
            name="throws_search",
            description="Search THROWS relations in graph"
        )
        self.search_engine = search_engine
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Search for THROWS relations."""
        if not self.search_engine:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="SearchEngine not initialized"
            )
        
        error_type = kwargs.get("error_type", "UnknownException")
        client = kwargs.get("client")
        model = kwargs.get("model", "Pro/zai-org/GLM-5")
        question = f"Which methods in HarmonyOS throw {error_type}? How to handle them?"
        
        try:
            result = self.search_engine.answer_question(
                client=client,
                model=model,
                question=question,
                mode="local"
            )
            
            return ToolExecutionResult(
                status="success",
                output={
                    "found": True,
                    "answer": result.answer,
                    "mode": result.mode,
                    "sources": result.sources
                }
            )
        
        except Exception as e:
            logger.error(f"THROWS search failed: {e}")
            return ToolExecutionResult(
                status="error",
                output=None,
                error=str(e)
            )


class L1SkillSearchTool(BaseTool):
    """Search 56+ Cangjie language basic skills."""
    
    def __init__(self, skills_path: Path):
        super().__init__(
            name="l1_skill_search",
            description="Search 56+ Cangjie language basic skills"
        )
        self.skills_path = skills_path
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute L1 skill search."""
        keywords = kwargs.get("keywords", [])
        matched_skills = []
        
        if not self.skills_path.exists():
            logger.warning(f"L1 skills directory not found: {self.skills_path}")
            return ToolExecutionResult(
                status="error",
                output=[],
                error="L1 skills directory not found"
            )
        
        for skill_dir in self.skills_path.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            try:
                fcontent = skill_md.read_text(encoding="utf-8", errors="ignore")
                matched_keywords = []
                
                for keyword in keywords:
                    if keyword.lower() in fcontent.lower() or keyword.lower() in skill_dir.name.lower():
                        matched_keywords.append(keyword)
                
                if matched_keywords:
                    matched_skills.append({
                        "skill_name": skill_dir.name,
                        "path": str(skill_dir),
                        "matched_keywords": matched_keywords,
                        "file": str(skill_md),
                    })
            except Exception as e:
                logger.debug(f"Failed to read SKILL {skill_dir}: {e}")
        
        logger.info(f"L1 skill search completed, found {len(matched_skills)} matched skills")
        
        return ToolExecutionResult(
            status="success",
            output=matched_skills,
            metadata={"matched_count": len(matched_skills)}
        )


class L3DocumentSearchTool(BaseTool):
    """Search local HarmonyOS official docs."""
    
    def __init__(self, docs_base: Path):
        super().__init__(
            name="l3_document_search",
            description="Search local HarmonyOS official docs"
        )
        self.docs_base = docs_base
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute L3 document search."""
        keywords = kwargs.get("keywords", [])
        matched_docs = []
        
        if not self.docs_base.exists():
            logger.warning(f"L3 docs directory not found: {self.docs_base}")
            return ToolExecutionResult(
                status="error",
                output=[],
                error="L3 docs directory not found"
            )
        
        search_paths = [
            self.docs_base / "ui-dev" / "arkui-cj",
            self.docs_base / "syntax" / "source_zh_cn",
            self.docs_base / "stdlib" / "std",
        ]
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
            
            for md_file in search_path.rglob("*.md"):
                try:
                    fcontent = md_file.read_text(encoding="utf-8", errors="ignore")
                    matches = sum(fcontent.lower().count(kw.lower()) for kw in keywords)
                    
                    if matches > 0:
                        matched_docs.append({
                            "path": str(md_file.relative_to(self.docs_base)),
                            "file_name": md_file.name,
                            "matches": matches,
                        })
                except Exception:
                    continue
        
        matched_docs = list({doc["path"]: doc for doc in matched_docs}.values())
        matched_docs.sort(key=lambda x: x["matches"], reverse=True)
        matched_docs = matched_docs[:20]
        
        logger.info(f"L3 doc search completed, found {len(matched_docs)} matched docs")
        
        return ToolExecutionResult(
            status="success",
            output=matched_docs,
            metadata={"matched_count": len(matched_docs)}
        )


class IntelligentGraphSearchTool(BaseTool):
    """Intelligent graph search with intent routing and provenance tracing."""
    
    def __init__(self, search_engine):
        super().__init__(
            name="intelligent_graph_search",
            description="Intelligent graph search with intent routing and provenance tracing"
        )
        self.search_engine = search_engine
        self.intent_router = IntentRouter()
        self.evidence_extractor = EvidenceExtractor()
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute intelligent graph search."""
        question = kwargs.get("question", "")
        client = kwargs.get("client")
        model = kwargs.get("model", "Pro/zai-org/GLM-5")
        force_mode = kwargs.get("force_mode")
        
        result = {
            "found": False,
            "mode": "none",
            "answer": "",
            "context": None,
            "evidences": [],
            "provenance_text": "",
        }
        
        if not self.search_engine:
            return ToolExecutionResult(
                status="error",
                output=result,
                error="SearchEngine not initialized"
            )
        
        try:
            search_context = await self.intent_router.analyze(question)
            result["context"] = search_context
            
            logger.info(f"[GraphSearch] Intent analysis: {search_context.intent.complexity}, {search_context.intent.domain}, {search_context.intent.suggested_mode}")
            
            if force_mode:
                search_mode = force_mode
                logger.info(f"[GraphSearch] Using forced mode: {search_mode}")
            else:
                search_mode = search_context.intent.suggested_mode
                logger.info(f"[GraphSearch] Using auto-routing mode: {search_mode}")
            
            search_result = self.search_engine.answer_question(
                client=client,
                model=model,
                question=question,
                mode=search_mode
            )
            
            result["found"] = True
            result["mode"] = search_result.mode
            result["answer"] = search_result.answer
            
            evidences = self.evidence_extractor.extract_from_search_result(search_result.sources)
            result["evidences"] = evidences
            
            if evidences:
                result["provenance_text"] = self.evidence_extractor.format_for_verification(evidences)
                logger.info(f"[GraphSearch] Extracted {len(evidences)} evidence fragments")
            else:
                logger.warning(f"[GraphSearch] No evidence fragments extracted")
            
            result["search_context"] = {
                "complexity": search_context.intent.complexity,
                "domain": search_context.intent.domain,
                "mode": search_result.mode,
                "keywords": search_context.keywords,
                "entities": search_context.entities,
                "error_pattern": search_context.error_pattern,
            }
            
            logger.info(f"[GraphSearch] Completed, mode: {search_result.mode}")
        
        except Exception as e:
            logger.error(f"[GraphSearch] Failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return ToolExecutionResult(
            status="success" if result.get("found") else "error",
            output=result,
            metadata=result
        )


class KnowledgeExpertAgent(BaseAgent):
    """Knowledge Expert Agent with intelligent intent routing and InternalQuery support."""
    
    def __init__(
        self,
        blackboard: GlobalState,
        search_engine=None,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = """You are a HarmonyOS development knowledge expert. Responsible for knowledge retrieval and organization.

Your capabilities:
1. Retrieve and organize knowledge
2. Support global architecture problems
3. Use local search for API conflicts
4. Implement multi-layer knowledge retrieval
5. Ensure results are traceable
6. Handle InternalQuery by prioritizing Evolution.md, then searching GraphDistill for THROWS relations

Workflow:
- Process InternalQuery prioritized from blackboard
- Perform L1 skill search for basic knowledge
- Use GraphDistill for intelligent queries (auto-routed)
- Search L3 official documentation
- Record all findings to blackboard
"""
        
        super().__init__(
            name="KnowledgeExpertAgent",
            system_prompt=system_prompt,
            blackboard=blackboard,
            llm_client=llm_client,
            llm_model=llm_model
        )
        
        self.l1_skills_path = PROJECT_ROOT / ".opencode" / "skills" / "common-skill-l1"
        self.l3_docs_base = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "scripts" / "hm-docs"
        self.evolution_path = PROJECT_ROOT / ".opencode" / "skills" / "cangjie-dev-harmonyos" / "Evolution.md"
        self.search_engine = search_engine
    
    async def register_tools(self) -> None:
        """Register including intelligent graph search and evolution search."""
        await super().register_tools()
        logger.info(f"[{self.name}] Tools registered directly")
    
    async def _handle_internal_query(self, query: InternalQuery) -> List[Dict[str, Any]]:
        """Handle InternalQuery from DevOps Agent."""
        logger.info(f"[{self.name}] Handling InternalQuery: {query.query_id}")
        
        solutions = []
        
        # Step 1: Search Evolution.md
        logger.info(f"[{self.name}] Step 1: Searching Evolution.md...")
        evolution_tool = EvolutionSearchTool(self.evolution_path)
        error_keywords = self._extract_error_keywords(query.error_message)
        evolution_result = await evolution_tool.execute(error_keywords=error_keywords)
        
        if evolution_result.status == "success":
            evolution_solutions = evolution_result.output
            if evolution_solutions:
                logger.info(f"[{self.name}] Found {len(evolution_solutions)} solutions in Evolution.md")
                
                for sol in evolution_solutions[:3]:
                    solutions.append({
                        "source": "Evolution.md",
                        "description": sol.get("solution_text", ""),
                        "confidence": 0.9,
                        "match_score": sol.get("match_score"),
                    })
        
        # Step 2: If no solution in Evolution.md, search GraphDistill for THROWS relations
        if len(solutions) == 0 and query.error_type:
            logger.info(f"[{self.name}] Step 2: Searching GraphDistill for THROWS relations...")
            
            throws_tool = ThrowsRelationSearchTool(self.search_engine)
            throws_result = await throws_tool.execute(
                error_type=query.error_type or "UnknownException",
                client=self.llm_client,
                model=self.llm_model
            )
            
            if throws_result.status == "success":
                output = throws_result.output
                if output and output.get("found"):
                    logger.info(f"[{self.name}] Found THROWS relation information")
                    solutions.append({
                        "source": "GraphDistill (THROWS)",
                        "description": output.get("answer", ""),
                        "confidence": 0.8,
                        "evidences": output.get("sources", []),
                    })
        
        # Step 3: If still no solution, fallback to general knowledge search
        if len(solutions) == 0:
            logger.info(f"[{self.name}] Step 3: Fallback to general knowledge search...")
            error_keywords = self._extract_error_keywords(query.error_message + " " + query.build_log)
            
            l1_tool = L1SkillSearchTool(self.l1_skills_path)
            l1_result = await l1_tool.execute(keywords=error_keywords)
            
            if l1_result.status == "success":
                l1_skills = l1_result.output
                if l1_skills:
                    solutions.append({
                        "source": "L1 Skills",
                        "description": f"Refer to relevant skills: {', '.join([s['skill_name'] for s in l1_skills[:3]])}",
                        "confidence": 0.7,
                        "skills": l1_skills,
                    })
        
        # Add query information to solutions
        for sol in solutions:
            sol["query_id"] = query.query_id
            sol["timestamp"] = datetime.datetime.now().isoformat()
        
        return solutions
    
    def _extract_error_keywords(self, error_text: str) -> List[str]:
        """Extract error keywords from error text."""
        if not error_text:
            return []
        
        keywords = []
        
        error_matches = re.findall(r'\b[A-Z][a-zA-Z]*(?:Error|Exception)\b', error_text)
        keywords.extend(error_matches)
        
        if "Incompatible" in error_text:
            keywords.append("incompatible")
        if "Permission" in error_text or "Denied" in error_text:
            keywords.append("permission")
        if "undefined" in error_text.lower():
            keywords.append("undefined")
        if "undeclared" in error_text.lower():
            keywords.append("undeclared")
        
        return list(set(keywords))
    
    async def process(self) -> Dict[str, Any]:
        """Execute knowledge retrieval with intelligent on-demand capability (L1-L2-L3)."""
        logger.info(f"[{self.name}] Starting knowledge retrieval with on-demand logic...")
        
        technical_analysis = await self.blackboard.get("technical_analysis")
        
        if not technical_analysis:
            raise ValueError(f"[{self.name}] No technical analysis found on blackboard")
        
        keywords = technical_analysis.get("technical_keywords", [])
        ui_components = technical_analysis.get("ui_components", [])
        
        if not keywords and not ui_components:
            logger.warning(f"[{self.name}] No technical keywords, skipping knowledge retrieval")
            return {
                "agent": self.name,
                "success": True,
                "skipped": True,
                "reason": "No technical keywords"
            }
        
        results = {
            "l1_skills": [],
            "graph_search": {},
            "l3_documents": [],
            "summary": "",
            "decision_path": [],  # 记录决策路径
        }
        
        # === Step 1: L1 skill search (always execute, baseline) ===
        logger.info(f"[{self.name}] Step 1: L1 skill search (baseline)...")
        l1_tool = L1SkillSearchTool(self.l1_skills_path)
        l1_result = await l1_tool.execute(keywords=keywords)
        results["l1_skills"] = l1_result.output if l1_result.status == "success" else []
        results["decision_path"].append("Step 1: L1 search → started")
        
        # === Smart Decision 1: Is L1 sufficient? ===
        l1_sufficient = await self._is_l1_sufficient(
            results["l1_skills"],
            keywords,
            technical_analysis
        )
        
        if l1_sufficient["status"]:
            logger.info(f"[{self.name}] L1 search is sufficient: {l1_sufficient['reason']}")
            results["decision_path"].append(f"Step 2: L1 sufficient → skip L2 and L3")
            results["summary"] = f"Found {len(results['l1_skills'])} L1 skills (sufficient)"
            
            await self.blackboard.update("knowledge_results", results, agent_name=self.name)
            
            return {
                "agent": self.name,
                "success": True,
                "result": results,
                "decision_summary": "L1 baseline search was sufficient"
            }
        
        # === Step 2: L2 Graph search (only when L1 insufficient AND has search_engine) ===
        results["decision_path"].append("Step 2: L1 insufficient → proceed to L2")
        logger.info(f"[{self.name}] L1 insufficient, proceeding...")
        
        if not self.search_engine:
            logger.warning(f"[{self.name}] No search engine available, skipping L2")
        else:
            logger.info(f"[{self.name}] Step 2: GraphDistill search (when L1 insufficient)...")
            
            ui_component_list = [comp.get("component", "") for comp in ui_components]
            all_keywords = keywords + ui_component_list
            
            question = f"In HarmonyOS app development, how to implement features involving these: {', '.join(all_keywords)}?"
            
            graph_tool = IntelligentGraphSearchTool(self.search_engine)
            graph_result = await graph_tool.execute(
                question=question,
                client=self.llm_client,
                model=self.llm_model
            )
            results["graph_search"] = graph_result.output if graph_result.status == "success" else {}
            results["decision_path"].append("Step 3: L2 search completed")
            
            if results["graph_search"].get("found"):
                provenance_data = {
                    "context": results["graph_search"].get("context"),
                    "evidences": results["graph_search"].get("evidences"),
                    "provenance_text": results["graph_search"].get("provenance_text"),
                    "search_context": results["graph_search"].get("search_context"),
                }
                await self.blackboard.update("graph_provenance", provenance_data, agent_name=self.name)
                logger.info(f"[{self.name}] Graph provenance info written to blackboard")
        
        # === Smart Decision 2: Is L1+L2 sufficient? ===
        l1l2_sufficient = await self._is_l1l2_sufficient(
            results["l1_skills"],
            results["graph_search"],
            technical_analysis
        )
        
        if l1l2_sufficient["status"]:
            logger.info(f"[{self.name}] L1+L2 is sufficient: {l1l2_sufficient['reason']}")
            results["decision_path"].append(f"Step 4: L1+L2 sufficient → skip L3")
            results["summary"] = f"L1 ({len(results['l1_skills'])} skills) + GraphDistill (sufficient)"
            
            await self.blackboard.update("knowledge_results", results, agent_name=self.name)
            
            return {
                "agent": self.name,
                "success": True,
                "result": results,
                "decision_summary": "L1 baseline + GraphDistill combination was sufficient"
            }
        
        # === Step 3: L3 document search (only when L1 and L2 are BOTH insufficient) ===
        results["decision_path"].append("Step 5: L1+L2 insufficient → proceed to L3")
        logger.info(f"[{self.name}] L1+L2 insufficient, proceeding to L3...")
        
        logger.info(f"[{self.name}] Step 3: L3 document search (when L1+L2 insufficient)...")
        l3_tool = L3DocumentSearchTool(self.l3_docs_base)
        l3_result = await l3_tool.execute(keywords=keywords)
        results["l3_documents"] = l3_result.output if l3_result.status == "success" else []
        results["decision_path"].append("Step 6: L3 search completed")
        
        # Build summary based on actual executed searches
        summary_parts = []
        if results["l1_skills"]:
            summary_parts.append(f"L1({len(results['l1_skills'])} skills)")
        if results["graph_search"].get("found"):
            mode = results["graph_search"].get("mode", "")
            summary_parts.append(f"GraphDistill({mode})")
        if results["l3_documents"]:
            summary_parts.append(f"L3({len(results['l3_documents'])} docs)")
        
        results["summary"] = " + ".join(summary_parts) if summary_parts else "No matching knowledge"
        results["decision_path"].append("Step 7: Knowledge retrieval completed")
        
        await self.blackboard.update("knowledge_results", results, agent_name=self.name)
        
        logger.info(f"[{self.name}] On-demand knowledge retrieval completed: {results['summary']}")
        logger.info(f"[{self.name}] Decision path: {' → '.join(results['decision_path'])}")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
            "decision_summary": f"Executed {'; '.join(results['decision_path'])}"
        }
    
    async def _is_l1_sufficient(
        self, 
        l1_skills: List[Dict[str, Any]], 
        keywords: List[str],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AI判断L1搜索结果是否足够解决问题。
        
        Args:
            l1_skills: L1搜索结果
            keywords: 技术关键词
            analysis: 技术分析结果
            
        Returns:
            {"status": bool, "reason": str}
        """
        if not self.llm_client:
            logger.warning(f"[{self.name}] No LLM client, using fallback logic")
            return {"status": False, "reason": "No LLM client for intelligent decision"}
        
        skill_names = [s.get("skill_name", "") for s in l1_skills]
        ui_components = [c.get("component", "") for c in analysis.get("ui_components", [])]
        data_structures = [d.get("name", "") for d in analysis.get("data_structures", [])]
        
        prompt = f"""你是HarmonyOS开发知识专家。请判断当前的L1搜索结果是否足够支持用户需求。

【上下文信息】
- 用户需求的技术关键词: {keywords}
- 需要的UI组件: {ui_components}
- 需要的数据结构: {data_structures}
- L1搜索找到的技能: {skill_names}

【判断标准】
请根据项目的具体需求，判断L1技能是否已经包含了实现需求所需的核心知识：
- 如果L1技能覆盖了所有关键组件和数据结构，则认为足够
- 如果只是部分覆盖，或者缺少核心知识，则认为不够
- 考虑项目的复杂度和特殊需求

【输出格式】
判断结果: true 或 false
判断理由: 一句话说明为什么足够/不够（必须用中文）

只输出这两行，不要包含其他内容。"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content or ""
            
            if "判断结果: true" in content.lower():
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为L1足够"
                logger.info(f"[{self.name}] AI判断: L1足够 - {reason_match}")
                return {"status": True, "reason": reason_match}
            else:
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为L1不够"
                logger.info(f"[{self.name}] AI判断: L1不够 - {reason_match}")
                return {"status": False, "reason": reason_match}
        
        except Exception as e:
            logger.error(f"[{self.name}] AI判断失败: {e}")
            return {"status": False, "reason": f"AI判断失败: {str(e)}"}
    
    async def _is_l1l2_sufficient(
        self,
        l1_skills: List[Dict[str, Any]],
        graph_search: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AI判断L1+L2组合是否足够。
        
        Returns:
            {"status": bool, "reason": str}
        """
        if not self.llm_client:
            logger.warning(f"[{self.name}] No LLM client, using fallback logic")
            return {"status": False, "reason": "No LLM client for intelligent decision"}
        
        skill_names = [s.get("skill_name", "") for s in l1_skills]
        graph_answer = graph_search.get("answer", "")
        graph_found = graph_search.get("found", False)
        graph_mode = graph_search.get("mode", "")
        evidences_count = len(graph_search.get("evidences", []))
        ui_components = [c.get("component", "") for c in analysis.get("ui_components", [])]
        
        prompt = f"""你是HarmonyOS开发知识专家。请判断当前的L1技能+GraphDistill搜索组合是否足够支持用户需求。

【上下文信息】
- 用户需要的UI组件: {ui_components}
- L1搜索找到的技能: {skill_names}
- GraphDistill搜索:
  * 搜索模式: {graph_mode}
  * 是否找到结果: {graph_found}
  * 答案长度: {len(graph_answer)} 字符
  * 证据数量: {evidences_count}
  * 答案摘要: {graph_answer[:200] if graph_answer else '无'}

【判断标准】
请根据L1技能和GraphDistill的搜索结果，判断两者组合是否能够提供实现需求所需的知识：
- 如果GraphDistill找到了高质量的答案且与L1技能互补，则认为足够
- 如果GraphDistill没有找到有效答案，且L1技能又不全面，则认为不够
- 如果两者结合仍无法覆盖核心需求，则认为不够

【输出格式】
判断结果: true 或 false
判断理由: 一句话说明为什么足够/不够（必须用中文）

只输出这两行，不要包含其他内容。"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            content = response.choices[0].message.content or ""
            
            if "判断结果: true" in content.lower():
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为L1+L2足够"
                logger.info(f"[{self.name}] AI判断: L1+L2足够 - {reason_match}")
                return {"status": True, "reason": reason_match}
            else:
                reason_match = content.split("判断理由:")[1].strip() if "判断理由:" in content else "AI认为L1+L2不够"
                logger.info(f"[{self.name}] AI判断: L1+L2不够 - {reason_match}")
                return {"status": False, "reason": reason_match}
        
        except Exception as e:
            logger.error(f"[{self.name}] AI判断失败: {e}")
            return {"status": False, "reason": f"AI判断失败: {str(e)}"}
