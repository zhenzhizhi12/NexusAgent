"""
Internal Query System - Collaborative internal query mechanism between agents

Supports internal dialogue protocol between DevOps Agent and Knowledge Expert Agent
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class QueryPriority(Enum):
    """Query priority levels."""
    CRITICAL = "critical"      # Complete build failure
    HIGH = "high"             # Multiple retry failures
    MEDIUM = "medium"         # Warnings or partial failures
    LOW = "low"               # Suggestions/optimizations


class QueryStatus(Enum):
    """Query status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SOLUTION_FOUND = "solution_found"
    NO_SOLUTION = "no_solution"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class InternalQuery:
    """Internal query request for agent-to-agent communication."""

    query_id: str                          # Unique query ID
    sender: str                            # Sender agent name
    recipient: str                         # Recipient agent name
    question: str                          # Query question
    priority: QueryPriority                # Priority
    status: QueryStatus                    # Status

    # Query content
    error_type: Optional[str] = None       # Error type
    error_message: str = ""                # Error message
    build_log: str = ""                    # Build log

    # Context information
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Result data
    solutions: List[Dict[str, Any]] = field(default_factory=list)
    evaluation_results: List[Dict[str, Any]] = field(default_factory=list)
    selected_solution: Optional[Dict[str, Any]] = None
    final_outcome: Optional[str] = None

    # Collaboration history
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)

    def add_message(self, sender: str, content: str, message_type: str = "info") -> None:
        """Add message to conversation history.

        Args:
            sender: Sender name
            content: Message content
            message_type: Message type
        """
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "content": content,
            "type": message_type
        })

    def get_conversation_summary(self) -> str:
        """Get conversation summary.

        Returns:
            Formatted conversation summary
        """
        if not self.conversation_history:
            return "No conversation history"

        lines = [f"Query ID: {self.query_id}"]
        lines.append(f"Status: {self.status.value}")
        lines.append(f"Priority: {self.priority.value}")
        lines.append("\nConversation Flow:")

        for i, msg in enumerate(self.conversation_history, 1):
            lines.append(f"{i}. [{msg['sender']} @ {msg['timestamp']}]")
            lines.append(f"   {msg['content'][:100]}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "query_id": self.query_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "question": self.question,
            "priority": self.priority.value,
            "status": self.status.value,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "build_log": self.build_log,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "solutions": self.solutions,
            "evaluation_results": self.evaluation_results,
            "selected_solution": self.selected_solution,
            "final_outcome": self.final_outcome,
            "conversation_history": self.conversation_history,
        }


@dataclass
class QueryResponse:
    """Query response."""

    query_id: str                          # Corresponding query ID
    response_from: str                     # Responder
    success: bool                          # Success flag
    message: str                           # Response message
    solutions: List[Dict[str, Any]] = field(default_factory=list)  # Solution list
    confidence: float = 0.0                # Confidence level
    source_evidence: List[Dict[str, Any]] = field(default_factory=list)  # Evidence sources

    timestamp: datetime = field(default_factory=datetime.now)

    def add_solution(self, solution: Dict[str, Any]) -> None:
        """Add solution.

        Args:
            solution: Solution dictionary
        """
        self.solutions.append(solution)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "query_id": self.query_id,
            "response_from": self.response_from,
            "success": self.success,
            "message": self.message,
            "solutions": self.solutions,
            "confidence": self.confidence,
            "source_evidence": self.source_evidence,
            "timestamp": self.timestamp.isoformat()
        }


class ConversationFlow:
    """Conversation flow manager."""

    def __init__(self):
        """Initialize conversation flow manager."""
        self.queries: Dict[str, InternalQuery] = {}
        self.active_queries: List[str] = []

    def create_query(
        self,
        sender: str,
        recipient: str,
        question: str,
        priority: QueryPriority,
        error_type: Optional[str] = None,
        error_message: str = "",
        build_log: str = ""
    ) -> InternalQuery:
        """Create new internal query.

        Args:
            sender: Sender agent name
            recipient: Recipient agent name
            question: Query question
            priority: Query priority
            error_type: Error type
            error_message: Error message
            build_log: Build log

        Returns:
            Created InternalQuery instance
        """
        import uuid

        query_id = f"query-{uuid.uuid4().hex[:8]}"
        query = InternalQuery(
            query_id=query_id,
            sender=sender,
            recipient=recipient,
            question=question,
            priority=priority,
            status=QueryStatus.PENDING,
            error_type=error_type,
            error_message=error_message,
            build_log=build_log
        )

        self.queries[query_id] = query
        self.active_queries.append(query_id)

        return query

    def get_query(self, query_id: str) -> Optional[InternalQuery]:
        """Get query by ID.

        Args:
            query_id: Query ID

        Returns:
            InternalQuery instance or None
        """
        return self.queries.get(query_id)

    def update_query_status(self, query_id: str, status: QueryStatus, message: str = "") -> None:
        """Update query status.

        Args:
            query_id: Query ID
            status: New status
            message: Optional message
        """
        query = self.get_query(query_id)
        if query:
            query.status = status
            if message:
                query.add_message("system", message)

    def complete_query(
        self,
        query_id: str,
        success: bool,
        outcome: str,
        selected_solution: Optional[Dict[str, Any]] = None
    ) -> None:
        """Complete query.

        Args:
            query_id: Query ID
            success: Success flag
            outcome: Final outcome description
            selected_solution: Selected solution
        """
        query = self.get_query(query_id)
        if query:
            query.status = QueryStatus.COMPLETED if success else QueryStatus.FAILED
            query.final_outcome = outcome
            query.selected_solution = selected_solution
            query.add_message("system", f"Query completed: {outcome}")

            if query_id in self.active_queries:
                self.active_queries.remove(query_id)

    def get_active_queries(self, agent_name: str) -> List[InternalQuery]:
        """Get active queries for a specific agent.

        Args:
            agent_name: Agent name

        Returns:
            List of active InternalQuery instances
        """
        return [
            query for query_id in self.active_queries
            if (query := self.get_query(query_id)) and
               (query.recipient == agent_name or query.sender == agent_name)
        ]

    def get_conversation_flow_summary(self) -> Dict[str, Any]:
        """Get summary of all conversation flows.

        Returns:
            Dictionary with flow statistics
        """
        return {
            "total_queries": len(self.queries),
            "active_queries": len(self.active_queries),
            "completed": sum(1 for q in self.queries.values() if q.status == QueryStatus.COMPLETED),
            "failed": sum(1 for q in self.queries.values() if q.status == QueryStatus.FAILED),
            "pending": sum(1 for q in self.queries.values() if q.status == QueryStatus.PENDING),
            "processing": sum(1 for q in self.queries.values() if q.status == QueryStatus.PROCESSING),
        }
