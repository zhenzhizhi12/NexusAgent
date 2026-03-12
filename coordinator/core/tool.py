"""
Base Tool System for NexusAgent

This module provides the foundation for all tools used by agents in the NexusAgent system.
All tools inherit from BaseTool and follow a standardized interface.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


logger = logging.getLogger("BaseTool")


@dataclass
class ToolExecutionResult:
    """Standardized result structure for tool execution.
    
    Attributes:
        status: Execution status (success, failure, error)
        output: Tool output (stdout, data, etc.)
        error: Error message if execution failed
        metadata: Additional metadata about the execution
    """
    status: str  # "success" | "failure" | "error"
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status,
            "output": str(self.output) if self.output is not None else None,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ToolArgument:
    """Tool argument definition.
    
    Attributes:
        name: Argument name
        type: Argument type (str, int, Path, etc.)
        description: Argument description
        required: Whether argument is required
        default: Default value (if not required)
    """
    name: str
    type: type
    description: str
    required: bool = True
    default: Any = None


class BaseTool(ABC):
    """Abstract base class for all tools in NexusAgent.
    
    Every tool must:
    1. Define name and description
    2. Define its argument schema
    3. Implement the async execute() method
    4. Return a ToolExecutionResult
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        args_schema: Optional[Dict[str, ToolArgument]] = None
    ):
        """Initialize the tool.
        
        Args:
            name: Unique tool identifier
            description: Human-readable description of what the tool does
            args_schema: Dictionary of argument definitions
        """
        self.name = name
        self.description = description
        self.args_schema = args_schema or {}
        
        logger.debug(f"[{self.__class__.__name__}] Initialized: {self.name}")
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute the tool with given arguments.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            ToolExecutionResult with status, output, and error info
        """
        pass
    
    def validate_args(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate arguments against schema.
        
        Args:
            **kwargs: Arguments to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        for arg_name, arg_def in self.args_schema.items():
            if arg_def.required and arg_name not in kwargs:
                return False, f"Required argument missing: {arg_name}"
            
            if arg_name in kwargs:
                value = kwargs[arg_name]
                if not isinstance(value, arg_def.type):
                    return False, f"Argument '{arg_name}' must be of type {arg_def.type.__name__}, got {type(value).__name__}"
        
        return True, None
    
    async def safe_execute(self, **kwargs) -> ToolExecutionResult:
        """Safely execute with validation and error handling.
        
        Args:
            **kwargs: Tool arguments
            
        Returns:
            ToolExecutionResult with error handling
        """
        try:
            is_valid, error_msg = self.validate_args(**kwargs)
            if not is_valid:
                return ToolExecutionResult(
                    status="error",
                    output=None,
                    error=f"Validation failed: {error_msg}"
                )
            
            logger.info(f"[{self.name}] Executing with args: {list(kwargs.keys())}")
            result = await self.execute(**kwargs)
            logger.info(f"[{self.name}] Execution completed with status: {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] Execution failed: {e}", exc_info=True)
            return ToolExecutionResult(
                status="failure",
                output=None,
                error=str(e),
                metadata={"exception_type": type(e).__name__}
            )
    
    def __repr__(self) -> str:
        return f"BaseTool(name={self.name}, args={len(self.args_schema)})"
