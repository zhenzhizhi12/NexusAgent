import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import re

logger = logging.getLogger("IntentRouter")


@dataclass
class IntentAnalysis:
    """Intent analysis result"""
    
    complexity: str
    domain: str
    requires_global: bool
    requires_local: bool
    suggested_mode: str
    confidence: float
    reasoning: str = ""


@dataclass  
class SearchContext:
    """Search context"""
    
    original_question: str
    intent: IntentAnalysis
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    error_pattern: Optional[str] = None


class IntentRouter:
    """Intelligent intent router"""
    
    def __init__(self):
        self.global_keywords = [
            "architecture", "design", "mechanism", "pattern", 
            "system", "global", "principle"
        ]
        
        self.local_keywords = [
            "error", "exception", "api", "conflict", 
            "incompatible", "method", "function"
        ]
        
        self.error_patterns = [
            r"Exception:\w+",
            r"Error:\w+",
            r"\w+Exception",
            r"Incompatible\w*",
        ]
    
    async def analyze(self, question: str) -> SearchContext:
        """Analyze question and return intent and context"""
        context = SearchContext(
            original_question=question,
            intent=IntentAnalysis(
                complexity="medium",
                domain="other",
                requires_global=False,
                requires_local=False,
                suggested_mode="auto",
                confidence=0.5,
                reasoning=""
            ),
            keywords=[],
            entities=[]
        )
        
        if not question:
            return context
        
        lower_q = question.lower()
        
        # Check for global intent keywords
        global_matches = [kw for kw in self.global_keywords if kw.lower() in lower_q]
        context.intent.requires_global = len(global_matches) > 0
        
        # Check for local search keywords  
        local_matches = [kw for kw in self.local_keywords if kw.lower() in lower_q]
        context.intent.requires_local = len(local_matches) > 0
        
        # Determine domain
        if "error" in question or "exception" in question:
            context.intent.domain = "exception"
        elif "api" in lower_q:
            context.intent.domain = "api"
        elif any(kw in lower_q for kw in ["architecture", "design", "system"]):
            context.intent.domain = "architecture"
        
        # Determine complexity
        if context.intent.requires_global and len(global_matches) > 1:
            context.intent.complexity = "complex"
            context.intent.confidence = 0.8
        elif context.intent.requires_local:
            context.intent.complexity = "simple"
            context.intent.confidence = 0.7
        else:
            context.intent.complexity = "medium"
            context.intent.confidence = 0.5
        
        # Suggest search mode
        if context.intent.requires_global and context.intent.complexity in ["complex", "medium"]:
            context.intent.suggested_mode = "global"
            context.intent.reasoning = f"Global architecture keywords detected: {global_matches[:3]}"
        elif context.intent.requires_local and context.intent.complexity == "simple":
            context.intent.suggested_mode = "local"
            context.intent.reasoning = f"Local search keywords detected: {local_matches[:3]}"
        elif context.intent.requires_global and context.intent.requires_local:
            context.intent.suggested_mode = "hybrid"
            context.intent.reasoning = "Both global and local needs detected, suggest hybrid mode"
        else:
            context.intent.suggested_mode = "auto"
            context.intent.reasoning = "Using auto mode for adaptive routing"
        
        # Extract keywords
        context.keywords = global_matches + local_matches
        
        logger.info(f"[IntentRouter] Analysis complete: complexity={context.intent.complexity}, domain={context.intent.domain}, mode={context.intent.suggested_mode}")
        
        return context


class EvidenceExtractor:
    """Evidence extractor for provenance tracing"""
    
    def extract_from_search_result(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract evidence from search result sources"""
        evidences = []
        
        if not sources:
            return evidences
        
        for source in sources:
            if not source:
                continue
            
            evidence = {
                "entity_id": source.get("entity_id", source.get("id", "unknown")),
                "entity_name": source.get("name", ""),
                "entity_type": source.get("entity_type", ""),
                "content": source.get("content", ""),
                "source_file": source.get("file_path", ""),
                "line_number": source.get("line_number", -1),
            }
            
            if evidence["content"]:
                evidences.append(evidence)
        
        # Deduplicate
        seen = set()
        unique_evidences = []
        for ev in evidences:
            ev_key = (ev["entity_id"], ev["content"][:50])
            if ev_key not in seen:
                seen.add(ev_key)
                unique_evidences.append(ev)
        
        logger.debug(f"[EvidenceExtractor] Extracted {len(unique_evidences)} evidences")
        
        return unique_evidences
    
    def format_for_verification(self, evidences: List[Dict[str, Any]]) -> str:
        """Format evidences for verification"""
        if not evidences:
            return "No evidence for verification"
        
        lines = []
        lines.append("=" * 80)
        lines.append("Provenance Trace")
        lines.append("=" * 80)
        
        for i, ev in enumerate(evidences, 1):
            lines.append(f"\n[Evidence {i}]")
            lines.append(f"Entity: {ev.get('entity_name', ev.get('entity_id', 'unknown'))}")
            lines.append(f"Type: {ev.get('entity_type', 'unknown')}")
            lines.append(f"Source: {ev.get('source_file', 'unknown')}:{ev.get('line_number', '?')}")
            lines.append(f"Content: {ev.get('content', '')[:300]}...")
        
        return "\n".join(lines)
