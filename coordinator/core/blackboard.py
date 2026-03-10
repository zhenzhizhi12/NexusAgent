import asyncio
import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from coordinator.core.internal_query import InternalQuery, QueryPriority, QueryStatus, ConversationFlow

logger = logging.getLogger("GlobalState")


class AgentStatus(Enum):
    """Status of an agent in the workflow."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Agent message for passing information between agents via the blackboard.

    Attributes:
        sender: Sender agent name
        content: Message content
        timestamp: Message timestamp
        message_type: Message type
    """
    sender: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    message_type: str = "info"


class GlobalState:
    """Blackboard system - shared global state for all agents.

    Core Features:
    1. Store and manage shared state data
    2. Support asynchronous message passing between agents
    3. Record workflow execution history
    4. Provide event notification mechanism

    Design Principles:
    - Thread-safe (using asyncio locks)
    - Immutable history (append-only)
    - Agents can only modify target state via messages
    """

    def __init__(self):
        """Initialize the global state."""
        self._lock = asyncio.Lock()

        # Core state data
        self.data: Dict[str, Any] = {
            "requirement": None,
            "technical_analysis": {},
            "knowledge_results": {},
            "generated_code": None,
            "dependencies": {},
            "build_results": [],
            "evolution_records": [],
            "project_root": None,
        }

        # Agent status tracking
        self.agent_states: Dict[str, AgentStatus] = {}

        # Message queue (agent mailboxes)
        self.messages: List[AgentMessage] = []

        # Agent message subscriptions
        self.message_subscribers: Dict[str, List[str]] = {}

        # Execution history
        self.history: List[Dict[str, Any]] = []

        logger.info("GlobalState initialized")

    async def update(self, key: str, value: Any, agent_name: str = "system") -> None:
        """Update state data.

        Args:
            key: State key
            value: State value
            agent_name: Operating agent name
        """
        async with self._lock:
            old_value = self.data.get(key)
            self.data[key] = value

            # Record history
            self._record_history(
                action="update",
                agent=agent_name,
                key=key,
                old_value=old_value,
                new_value=value,
            )

            logger.debug(f"[{agent_name}] Updated state: {key} = {type(value).__name__}")

    async def get(self, key: str, default: Any = None) -> Any:
        """Get state data (read-only, no lock needed).

        Args:
            key: State key
            default: Default value

        Returns:
            State value
        """
        return self.data.get(key, default)

    async def update_agent_status(self, agent_name: str, status: AgentStatus) -> None:
        """Update agent status.

        Args:
            agent_name: Agent name
            status: New status
        """
        async with self._lock:
            old_status = self.agent_states.get(agent_name)
            self.agent_states[agent_name] = status

            # Record history
            self._record_history(
                action="agent_status_change",
                agent=agent_name,
                old_status=old_status.value if old_status else None,
                new_status=status.value,
            )

            logger.info(f"Agent status updated: {agent_name} -> {status.value}")

    async def post_message(
        self,
        sender: str,
        content: Any,
        message_type: str = "info",
        recipients: Optional[List[str]] = None
    ) -> None:
        """Send message to blackboard.

        Args:
            sender: Sender agent name
            content: Message content
            message_type: Message type
            recipients: List of recipients (None means broadcast)
        """
        message = AgentMessage(
            sender=sender,
            content=content,
            message_type=message_type
        )

        async with self._lock:
            self.messages.append(message)

            # Record history
            self._record_history(
                action="message",
                sender=sender,
                recipients=recipients or "broadcast",
                message_type=message_type,
                content_preview=str(content)[:100] if content else "",
            )

            logger.debug(f"[Message] {sender} -> {recipients or 'broadcast'}: {message_type}")

    async def get_messages(
        self,
        agent_name: str,
        since: Optional[datetime] = None
    ) -> List[AgentMessage]:
        """Get messages for a specific agent.

        Args:
            agent_name: Agent name
            since: Timestamp to filter from

        Returns:
            List of messages
        """
        async with self._lock:
            if since:
                return [
                    msg for msg in self.messages
                    if msg.timestamp >= since and (
                        msg.sender != agent_name
                    )
                ]
            else:
                return [msg for msg in self.messages if msg.sender != agent_name]

    async def subscribe_to_agent(self, subscriber: str, target: str) -> None:
        """Subscribe to an agent's messages.

        Args:
            subscriber: Subscriber name
            target: Target agent name
        """
        async with self._lock:
            if target not in self.message_subscribers:
                self.message_subscribers[target] = []
            if subscriber not in self.message_subscribers[target]:
                self.message_subscribers[target].append(subscriber)
                logger.info(f"[Subscribe] {subscriber} subscribed to {target}")

    def _record_history(self, **kwargs) -> None:
        """Record history (internal method, already locked).

        Args:
            **kwargs: History record data
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.history.append(record)

    async def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current state snapshot (without full history).

        Returns:
            State snapshot
        """
        return {
            "data": {k: type(v).__name__ for k, v in self.data.items()},
            "agent_states": {k: v.value for k, v in self.agent_states.items()},
            "message_count": len(self.messages),
            "history_count": len(self.history),
        }

    async def export_history(self, limit=50) -> List[Dict[str, Any]]:
        """Export execution history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of history records
        """
        return self.history[-limit:]

    async def export_to_json(self, filepath: Path) -> None:
        """Export complete state to JSON file.

        Args:
            filepath: Output file path
        """
        async with self._lock:
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "data": self.data,
                "agent_states": {k: v.value for k, v in self.agent_states.items()},
                "messages": [
                    {
                        "sender": msg.sender,
                        "content": str(msg.content),
                        "timestamp": msg.timestamp.isoformat(),
                        "type": msg.message_type,
                    }
                    for msg in self.messages[-20:]
                ],
                "history": self.history[-100:],
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"State exported to: {filepath}")

    async def reset(self) -> None:
        """Reset all state (for testing)."""
        async with self._lock:
            self.data.clear()
            self.data.update({
                "requirement": None,
                "technical_analysis": {},
                "knowledge_results": {},
                "generated_code": None,
                "dependencies": {},
                "build_results": [],
                "evolution_records": [],
                "project_root": None,
            })
            self.agent_states.clear()
            self.messages.clear()
            self.history.clear()
            self.message_subscribers.clear()

            logger.info("GlobalState reset")
