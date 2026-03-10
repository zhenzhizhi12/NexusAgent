import datetime
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from coordinator.agents.base_agent import BaseAgent, Tool
from coordinator.agents.intent_router import IntentRouter, EvidenceExtractor, SearchContext
from coordinator.core.blackboard import GlobalState
from coordinator.core.internal_query import InternalQuery, QueryPriority, QueryStatus

PROJECT_ROOT = Path(__file__).parent.parent.parent

logger = logging.getLogger("KnowledgeAgent")


class EvolutionSearchTool(Tool):
    """Evolution.md search tool"""
    
    def __init__(self, evolution_path: Path):
        super().__init__(name="evolution_search", description="Search Evolution.md for similar problems")
        self.evolution_path = evolution_path
    
    async def execute(self, error_keywords: List[str]) -> List[Dict[str, Any]]:
        """Search Evolution.md for similar errors"""
        matched_solutions = []
        
        if not self.evolution_path.exists():
            logger.warning(f"Evolution.md not found: {self.evolution_path}")
            return matched_solutions
        
        try:
            content = self.evolution_path.read_text(encoding="utf-8", errors="ignore")
            logger.info(f"Read Evolution.md ({len(content)} bytes)")
            
            # Extract solution sections
            import re
            sections = re.split(r'###\s+', content)
            
            for section in sections:
                if not section:
                    continue
                
                # Check if any keyword matches
                match_score = sum(section.lower().count(kw.lower()) for kw in error_keywords)
                
                if match_score > 0:
                    # Extract solution from section
                    lines = section.split('\n')
                    solution_text = '\n'.join(lines[3:])  # Skip title and date lines
                    
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
        
        return matched_solutions


class ThrowsRelationSearchTool(Tool):
    """THROWS relation search in graph"""
    
    def __init__(self, search_engine):
        super().__init__(name="throws_search", description="Search THROWS relations in graph")
        self.search_engine = search_engine
    
    async def execute(
        self,
        error_type: str,
        client=None,
        model="Pro/zai-org/GLM-5"
    ) -> Dict[str, Any]:
        """Search for THROWS relations"""
        if not self.search_engine:
            return {"found": False}
        
        question = f"Which methods in HarmonyOS throw {error_type}? How to handle them?"
        
        try:
            result = self.search_engine.answer_question(
                client=client,
                model=model,
                question=question,
                mode="local"  # Use local mode for entity-specific search
            )
            
            return {
                "found": True,
                "answer": result.answer,
                "mode": result.mode,
                "sources": result.sources
            }
        
        except Exception as e:
            logger.error(f"THROWS search failed: {e}")
            return {"found": False, "error": str(e)}


class L1SkillSearchTool(Tool):
    """L1 Skill Search Tool"""
    
    def __init__(self, skills_path: Path):
        super().__init__(name="l1_skill_search", description="Search 56+ Cangjie language basic skills")
        self.skills_path = skills_path
    
    async def execute(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Execute L1 skill search"""
        matched_skills = []
        
        if not self.skills_path.exists():
            logger.warning(f"L1 skills directory not found: {self.skills_path}")
            return matched_skills
        
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
        return matched_skills


class L3DocumentSearchTool(Tool):
    """L3 Document Search Tool"""
    
    def __init__(self, docs_base: Path):
        super().__init__(name="l3_document_search", description="Search local HarmonyOS official docs")
        self.docs_base = docs_base
    
    async def execute(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """Execute L3 document search"""
        matched_docs = []
        
        if not self.docs_base.exists():
            logger.warning(f"L3 docs directory not found: {self.docs_base}")
            return matched_docs
        
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
        return matched_docs


class IntelligentGraphSearchTool(Tool):
    """Intelligent Graph Search Tool with intent routing and provenance tracing"""
    
    def __init__(self, search_engine):
        super().__init__(
            name="intelligent_graph_search",
            description="Intelligent graph search with intent routing and provenance tracing"
        )
        self.search_engine = search_engine
        self.intent_router = IntentRouter()
        self.evidence_extractor = EvidenceExtractor()
    
    async def execute(
        self,
        question: str,
        client=None,
        model="Pro/zai-org/GLM-5",
        force_mode=None
    ) -> Dict[str, Any]:
        """Execute intelligent graph search"""
        result = {
            "found": False,
            "mode": "none",
            "answer": "",
            "context": None,
            "evidences": [],
            "provenance_text": "",
        }
        
        if not self.search_engine:
            result["reason"] = "SearchEngine not initialized"
            return result
        
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
        
        return result


class KnowledgeExpertAgent(BaseAgent):
    """Knowledge Expert Agent with intelligent intent routing and InternalQuery support"""
    
    def __init__(
        self,
        blackboard: GlobalState,
        search_engine=None,
        llm_client=None,
        llm_model="Pro/zai-org/GLM-5"
    ):
        system_prompt = "你是鸿蒙开发知识专家。负责检索和整理知识。支持全局架构问题。针对API冲突采用本地搜索。实现多层知识检索。确保结果可追溯。处理InternalQuery时，优先检查Evolution.md，然后使用GraphDistill搜索THROWS关系。"
        
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
        """Register tools including intelligent graph search and evolution search"""
        await super().register_tools()
        self.add_tool(L1SkillSearchTool(self.l1_skills_path))
        self.add_tool(IntelligentGraphSearchTool(self.search_engine))
        self.add_tool(L3DocumentSearchTool(self.l3_docs_base))
        self.add_tool(EvolutionSearchTool(self.evolution_path))
        self.add_tool(ThrowsRelationSearchTool(self.search_engine))
    
    async def _handle_internal_query(self, query: InternalQuery) -> List[Dict[str, Any]]:
        """Handle InternalQuery from DevOps Agent"""
        logger.info(f"[{self.name}] Handling InternalQuery: {query.query_id}")
        
        solutions = []
        
        # Step 1: Search Evolution.md
        logger.info(f"[{self.name}] Step 1: Searching Evolution.md...")
        error_keywords = self._extract_error_keywords(query.error_message)
        evolution_solutions = await self.call_tool("evolution_search", error_keywords)
        
        if evolution_solutions:
            logger.info(f"[{self.name}] Found {len(evolution_solutions)} solutions in Evolution.md")
            
            for sol in evolution_solutions[:3]:  # Top 3 matches
                solutions.append({
                    "source": "Evolution.md",
                    "description": sol["solution_text"],
                    "confidence": 0.9,
                    "match_score": sol["match_score"],
                })
        
        # Step 2: If no solution in Evolution.md, search GraphDistill for THROWS relations
        if len(solutions) == 0 and query.error_type:
            logger.info(f"[{self.name}] Step 2: Searching GraphDistill for THROWS relations...")
            
            throws_result = await self.call_tool(
                "throws_search",
                query.error_type or "UnknownException",
                self.llm_client,
                self.llm_model
            )
            
            if throws_result.get("found"):
                logger.info(f"[{self.name}] Found THROWS relation information")
                
                solutions.append({
                    "source": "GraphDistill (THROWS)",
                    "description": throws_result.get("answer", ""),
                    "confidence": 0.8,
                    "evidences": throws_result.get("sources", []),
                })
        
        # Step 3: If still no solution, fallback to general knowledge search
        if len(solutions) == 0:
            logger.info(f"[{self.name}] Step 3: Fallback to general knowledge search...")
            
            error_keywords = self._extract_error_keywords(query.error_message + " " + query.build_log)
            
            # Use L1 + Graph + L3 search
            l1_skills = await self.call_tool("l1_skill_search", error_keywords)
            
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
        """Extract error keywords from error text"""
        if not error_text:
            return []
        
        keywords = []
        
        # Extract error type
        error_matches = re.findall(r'\b[A-Z][a-zA-Z]*(?:Error|Exception)\b', error_text)
        keywords.extend(error_matches)
        
        # Extract common error indicators
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
        """Execute knowledge retrieval with InternalQuery support"""
        logger.info(f"[{self.name}] Starting knowledge retrieval...")
        
        # Check for InternalQuery first
        messages = await self.read_messages()
        internal_queries = [
            msg for msg in messages
            if isinstance(msg.content, dict) and 
               msg.content.get("type") == "internal_query" and
               msg.content.get("action") == "create" and
               msg.content.get("query", {}).get("recipient") == self.name
        ]
        
        if internal_queries:
            logger.info(f"[{self.name}] Found {len(internal_queries)} InternalQueries to process")
            
            # Process the first query
            query_data = internal_queries[0].content.get("query", {})
            
            # Reconstruct InternalQuery object
            from coordinator.core.internal_query import InternalQuery, QueryStatus
            query = InternalQuery(
                query_id=query_data.get("query_id"),
                sender=query_data.get("sender"),
                recipient=query_data.get("recipient"),
                question=query_data.get("question"),
                priority=getattr(QueryPriority, query_data.get("priority", "MEDIUM")),
                status=getattr(QueryStatus, query_data.get("status", "PENDING")),
                error_type=query_data.get("error_type"),
                error_message=query_data.get("error_message", ""),
                build_log=query_data.get("build_log", "")
            )
            
            # Handle the query
            solutions = await self._handle_internal_query(query)
            
            # Send response
            if solutions:
                await self.post_message(
                    {
                        "type": "internal_query",
                        "query_id": query.query_id,
                        "solutions": solutions,
                        "confidence": max(s.get("confidence", 0) for s in solutions),
                        "source_evidence": [s.get("evidences", []) for s in solutions if "evidences" in s],
                        "action": "respond"
                    },
                    message_type="query_response"
                )
                
                logger.info(f"[{self.name}] Sent response with {len(solutions)} solutions")
            else:
                logger.warning(f"[{self.name}] No solutions found for InternalQuery")
            
            return {
                "agent": self.name,
                "success": True,
                "result": {
                    "internal_query_processed": True,
                    "solutions_provided": len(solutions),
                }
            }
        
        # Normal knowledge retrieval flow
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
        }
        
        logger.info(f"[{self.name}] Step 1: L1 skill search...")
        l1_skills = await self.call_tool("l1_skill_search", keywords)
        results["l1_skills"] = l1_skills
        
        if self.search_engine and (keywords or ui_components):
            logger.info(f"[{self.name}] Step 2: Intelligent graph search...")
            
            ui_component_list = [comp.get("组件", "") for comp in ui_components]
            all_keywords = keywords + ui_component_list
            
            question = f"In HarmonyOS app development, how to implement features involving these components: {', '.join(all_keywords)}?"
            
            graph_result = await self.call_tool(
                "intelligent_graph_search",
                question,
                self.llm_client,
                self.llm_model,
                force_mode=None
            )
            results["graph_search"] = graph_result
            
            if graph_result.get("found"):
                provenance_data = {
                    "context": graph_result.get("context"),
                    "evidences": graph_result.get("evidences"),
                    "provenance_text": graph_result.get("provenance_text"),
                    "search_context": graph_result.get("search_context"),
                }
                await self.blackboard.update("graph_provenance", provenance_data, agent_name=self.name)
                logger.info(f"[{self.name}] Provenance info written to blackboard")
        
        logger.info(f"[{self.name}] Step 3: L3 document search...")
        l3_docs = await self.call_tool("l3_document_search", keywords)
        results["l3_documents"] = l3_docs
        
        summary_parts = []
        if l1_skills:
            summary_parts.append(f"Found {len(l1_skills)} L1 skills")
        if results["graph_search"].get("found"):
            mode = results["graph_search"].get("mode", "")
            summary_parts.append(f"Graph search completed ({mode} mode)")
        if l3_docs:
            summary_parts.append(f"Found {len(l3_docs)} documents")
        
        results["summary"] = ", ".join(summary_parts) if summary_parts else "No matching knowledge"
        
        await self.blackboard.update("knowledge_results", results, agent_name=self.name)
        
        logger.info(f"[{self.name}] Knowledge retrieval completed: {results['summary']}")
        
        return {
            "agent": self.name,
            "success": True,
            "result": results,
        }
