"""
File Browser Tool

Provides file system browsing capabilities:
- List directory contents
- Search for files by pattern
- Get file metadata
- Navigate directory tree
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, List

from coordinator.core.tool import BaseTool, ToolExecutionResult, ToolArgument


logger = logging.getLogger("FileBrowserTool")


class FileBrowserTool(BaseTool):
    """Browse and search the file system.
    
    Features:
    - List directory contents (with filtering)
    - Search files by name pattern
    - Get file/directory metadata
    - Recursive directory search
    - Check path type (file/directory)
    """
    
    def __init__(self):
        """Initialize the file browser tool."""
        super().__init__(
            name="file_browser",
            description="Browse and search file system: list, search, get metadata",
            args_schema={
                "action": ToolArgument(
                    name="action",
                    type=str,
                    description="Action: list, search, info, ls, find"
                ),
                "path": ToolArgument(
                    name="path",
                    type=str,
                    description="Directory or file path",
                    required=False,
                    default=None
                ),
                "pattern": ToolArgument(
                    name="pattern",
                    type=str,
                    description="Search pattern (e.g., '*.py', 'test_*')",
                    required=False,
                    default=None
                ),
                "recursive": ToolArgument(
                    name="recursive",
                    type=bool,
                    description="Search recursively (default: False)",
                    required=False,
                    default=False
                ),
                "limit": ToolArgument(
                    name="limit",
                    type=int,
                    description="Maximum results to return (default: 100)",
                    required=False,
                    default=100
                ),
                "filters": ToolArgument(
                    name="filters",
                    type=dict,
                    description="Filters: {'type': 'file' | 'dir', 'extension': '.py'}",
                    required=False,
                    default=None
                ),
            }
        )
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute file browser operation."""
        action = kwargs.get("action")
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")
        recursive = kwargs.get("recursive", False)
        limit = kwargs.get("limit", 100)
        filters = kwargs.get("filters")
        
        metadata = {
            "action": action,
            "path": path,
            "recursive": recursive,
        }
        
        try:
            # Default to current directory if no path
            if not path:
                path = "."
            
            target_path = Path(path)
            
            if action in ["list", "ls"]:
                return await self._list_directory(target_path, filters, limit, metadata)
            elif action in ["search", "find"]:
                return await self._search_files(target_path, pattern, recursive, filters, limit, metadata)
            elif action == "info":
                return await self._get_file_info(target_path, metadata)
            else:
                return ToolExecutionResult(
                    status="error",
                    output=None,
                    error=f"Unknown action: {action}",
                    metadata=metadata
                )
            
        except Exception as e:
            logger.error(f"[FileBrowser] {action} operation failed: {e}", exc_info=True)
            return ToolExecutionResult(
                status="error",
                output=None,
                error=str(e),
                metadata=metadata
            )
    
    async def _list_directory(
        self,
        path: Path,
        filters: Optional[Dict[str, Any]],
        limit: int,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """List directory contents."""
        if not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path not found: {path}",
                metadata=metadata
            )
        
        if not path.is_dir():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path is not a directory: {path}",
                metadata=metadata
            )
        
        items = []
        for item in path.iterdir():
            if self._matches_filters(item, filters):
                items.append({
                    "name": item.name,
                    "path": str(item.relative_to(path.parent)),
                    "full_path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                    "extension": item.suffix if item.is_file() else None,
                })
            
            if len(items) >= limit:
                break
        
        metadata.update({
            "item_count": len(items),
            "filters": filters,
        })
        
        logger.info(f"[FileBrowser] Listed directory: {path} ({len(items)} items)")
        return ToolExecutionResult(
            status="success",
            output=items,
            metadata=metadata
        )
    
    async def _search_files(
        self,
        path: Path,
        pattern: Optional[str],
        recursive: bool,
        filters: Optional[Dict[str, Any]],
        limit: int,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Search for files matching pattern."""
        if not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path not found: {path}",
                metadata=metadata
            )
        
        matches = []
        
        if recursive:
            # Recursive search
            search_target = path.rglob(pattern) if pattern else path.rglob("*")
        else:
            # Non-recursive search
            search_target = path.glob(pattern) if pattern else path.glob("*")
        
        for item in search_target:
            if self._matches_filters(item, filters):
                matches.append({
                    "name": item.name,
                    "path": str(item.relative_to(path.parent)),
                    "full_path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                    "extension": item.suffix if item.is_file() else None,
                })
            
            if len(matches) >= limit:
                break
        
        metadata.update({
            "match_count": len(matches),
            "pattern": pattern,
            "recursive": recursive,
        })
        
        logger.info(f"[FileBrowser] Found {len(matches)} matches for pattern '{pattern}'")
        return ToolExecutionResult(
            status="success",
            output=matches,
            metadata=metadata
        )
    
    async def _get_file_info(
        self,
        path: Path,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Get file or directory metadata."""
        if not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path not found: {path}",
                metadata=metadata
            )
        
        stat = path.stat()
        
        info = {
            "name": path.name,
            "path": str(path),
            "full_path": str(path.resolve()),
            "type": "directory" if path.is_dir() else "file",
            "size": stat.st_size if path.is_file() else None,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "extension": path.suffix if path.is_file() else None,
        }
        
        metadata.update({
            "type": info["type"],
        })
        
        logger.info(f"[FileBrowser] Got info for: {path}")
        return ToolExecutionResult(
            status="success",
            output=info,
            metadata=metadata
        )
    
    def _matches_filters(
        self,
        path: Path,
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if path matches filters."""
        if not filters:
            return True
        
        # Type filter
        if "type" in filters:
            type_filter = filters["type"]
            if type_filter == "file" and path.is_dir():
                return False
            if type_filter == "dir" and not path.is_dir():
                return False
        
        # Extension filter
        if "extension" in filters and path.is_file():
            ext_filter = filters["extension"]
            if not path.suffix.lower().endswith(ext_filter.lower()):
                return False
        
        # Name filter
        if "name" in filters:
            name_filter = filters["name"]
            if name_filter.lower() not in path.name.lower():
                return False
        
        return True
