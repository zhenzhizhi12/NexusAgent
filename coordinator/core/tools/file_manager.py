"""
File Manager Tool

Provides file operations: read, write, append, replace, and delete.
Supports text files with encoding and error handling.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from coordinator.core.tool import BaseTool, ToolExecutionResult, ToolArgument


logger = logging.getLogger("FileManagerTool")


class FileManagerTool(BaseTool):
    """Manage file operations.
    
    Features:
    - Read file contents
    - Write new files
    - Append to existing files
    - Replace content in files
    - Delete files
    - Check file existence
    - List directory contents
    - Auto-create directories as needed
    """
    
    def __init__(self):
        """Initialize the file manager tool."""
        super().__init__(
            name="file_manager",
            description="Manage files: read, write, append, replace, and delete operations",
            args_schema={
                "action": ToolArgument(
                    name="action",
                    type=str,
                    description="Action to perform: read, write, append, replace, delete, exists, list"
                ),
                "filepath": ToolArgument(
                    name="filepath",
                    type=str,
                    description="Path to the file"
                ),
                "content": ToolArgument(
                    name="content",
                    type=str,
                    description="Content for write/append/replace actions",
                    required=False,
                    default=None
                ),
                "encoding": ToolArgument(
                    name="encoding",
                    type=str,
                    description="File encoding (default: utf-8)",
                    required=False,
                    default="utf-8"
                ),
                "old_pattern": ToolArgument(
                    name="old_pattern",
                    type=str,
                    description="Pattern to replace (for replace action)",
                    required=False,
                    default=None
                ),
                "new_content": ToolArgument(
                    name="new_content",
                    type=str,
                    description="New content for replace action",
                    required=False,
                    default=None
                ),
                "create_dirs": ToolArgument(
                    name="create_dirs",
                    type=bool,
                    description="Create parent directories if they don't exist (default: True)",
                    required=False,
                    default=True
                ),
            }
        )
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute file operation."""
        action = kwargs.get("action")
        filepath = kwargs.get("filepath")
        content = kwargs.get("content")
        encoding = kwargs.get("encoding", "utf-8")
        old_pattern = kwargs.get("old_pattern")
        new_content = kwargs.get("new_content")
        create_dirs = kwargs.get("create_dirs", True)
        
        metadata = {
            "action": action,
            "filepath": filepath,
            "encoding": encoding,
        }
        
        try:
            path = Path(filepath) if filepath else None
            
            if action == "read":
                return await self._read_file(path, encoding, metadata)
            elif action == "write":
                return await self._write_file(path, content or "", encoding, create_dirs, metadata)
            elif action == "append":
                return await self._append_file(path, content or "", encoding, create_dirs, metadata)
            elif action == "replace":
                return await self._replace_in_file(path, old_pattern, new_content, encoding, metadata)
            elif action == "delete":
                return await self._delete_file(path, metadata)
            elif action == "exists":
                return await self._check_exists(path, metadata)
            elif action == "list":
                return await self._list_directory(path, metadata)
            else:
                return ToolExecutionResult(
                    status="error",
                    output=None,
                    error=f"Unknown action: {action}",
                    metadata=metadata
                )
            
        except Exception as e:
            logger.error(f"[FileManager] {action} operation failed: {e}", exc_info=True)
            return ToolExecutionResult(
                status="error",
                output=None,
                error=str(e),
                metadata=metadata
            )
    
    async def _read_file(
        self,
        path: Optional[Path],
        encoding: str,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Read file content."""
        if not path or not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"File not found: {path}",
                metadata=metadata
            )
        
        if not path.is_file():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path is not a file: {path}",
                metadata=metadata
            )
        
        content = path.read_text(encoding=encoding, errors='ignore')
        metadata.update({
            "size_bytes": len(content.encode(encoding)),
            "line_count": len(content.splitlines()),
        })
        
        logger.info(f"[FileManager] Read file: {path} ({len(content)} chars)")
        return ToolExecutionResult(
            status="success",
            output=content,
            metadata=metadata
        )
    
    async def _write_file(
        self,
        path: Optional[Path],
        content: str,
        encoding: str,
        create_dirs: bool,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Write content to file."""
        if not path:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="File path is required",
                metadata=metadata
            )
        
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(content, encoding=encoding)
        
        metadata.update({
            "size_bytes": len(content.encode(encoding)),
            "created": not path.exists(),
        })
        
        logger.info(f"[FileManager] Wrote file: {path} ({len(content)} chars)")
        return ToolExecutionResult(
            status="success",
            output=f"Successfully wrote {len(content)} characters to {path}",
            metadata=metadata
        )
    
    async def _append_file(
        self,
        path: Optional[Path],
        content: str,
        encoding: str,
        create_dirs: bool,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Append content to file."""
        if not path or not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Cannot append to non-existent file: {path}",
                metadata=metadata
            )
        
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)
        
        metadata.update({
            "appended_bytes": len(content.encode(encoding)),
        })
        
        logger.info(f"[FileManager] Appended to file: {path} ({len(content)} chars)")
        return ToolExecutionResult(
            status="success",
            output=f"Successfully appended {len(content)} characters to {path}",
            metadata=metadata
        )
    
    async def _replace_in_file(
        self,
        path: Optional[Path],
        old_pattern: Optional[str],
        new_content: Optional[str],
        encoding: str,
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Replace content in file."""
        if not path:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="File path is required",
                metadata=metadata
            )
        
        if not old_pattern or not new_content:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="Both old_pattern and new_content required for replace action",
                metadata=metadata
            )
        
        if not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"File not found: {path}",
                metadata=metadata
            )
        
        original_content = path.read_text(encoding=encoding)
        
        if old_pattern not in original_content:
            return ToolExecutionResult(
                status="failure",
                output=None,
                error=f"Pattern not found in file: {path}",
                metadata=metadata
            )
        
        new_full_content = original_content.replace(old_pattern, new_content)
        path.write_text(new_full_content, encoding=encoding)
        
        replacement_count = original_content.count(old_pattern)
        metadata.update({
            "replacements": replacement_count,
            "pattern_length": len(old_pattern),
        })
        
        logger.info(f"[FileManager] Replaced {replacement_count} occurrences in: {path}")
        return ToolExecutionResult(
            status="success",
            output=f"Successfully replaced {replacement_count} occurrence(s) in {path}",
            metadata=metadata
        )
    
    async def _delete_file(
        self,
        path: Optional[Path],
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Delete file or directory."""
        if not path or not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Path not found: {path}",
                metadata=metadata
            )
        
        if path.is_file():
            path.unlink()
            logger.info(f"[FileManager] Deleted file: {path}")
        else:
            import shutil
            shutil.rmtree(path)
            logger.info(f"[FileManager] Deleted directory: {path}")
        
        return ToolExecutionResult(
            status="success",
            output=f"Successfully deleted {path}",
            metadata=metadata
        )
    
    async def _check_exists(
        self,
        path: Optional[Path],
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """Check if path exists."""
        if not path:
            return ToolExecutionResult(
                status="error",
                output=None,
                error="Path is required",
                metadata=metadata
            )
        
        exists = path.exists()
        metadata.update({
            "exists": exists,
            "is_file": path.is_file() if exists else None,
            "is_dir": path.is_dir() if exists else None,
        })
        
        return ToolExecutionResult(
            status="success",
            output={
                "exists": exists,
                "is_file": path.is_file() if exists else False,
                "is_directory": path.is_dir() if exists else False,
            },
            metadata=metadata
        )
    
    async def _list_directory(
        self,
        path: Optional[Path],
        metadata: Dict[str, Any]
    ) -> ToolExecutionResult:
        """List directory contents."""
        if not path or not path.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Directory not found: {path}",
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
            items.append({
                "name": item.name,
                "path": str(item.relative_to(path.parent)),
                "full_path": str(item),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
                "extension": item.suffix if item.is_file() else None,
            })
        
        metadata.update({
            "item_count": len(items),
        })
        
        logger.info(f"[FileManager] Listed directory: {path} ({len(items)} items)")
        return ToolExecutionResult(
            status="success",
            output=items,
            metadata=metadata
        )


class FileReaderTool(FileManagerTool):
    """Specialized tool for reading files."""
    
    def __init__(self):
        super().__init__()
        self.name = "file_reader"
        self.description = "Read file contents (subset of file_manager)"
        self.args_schema = {
            "filepath": ToolArgument(
                name="filepath",
                type=str,
                description="Path to the file to read"
            ),
            "encoding": ToolArgument(
                name="encoding",
                type=str,
                description="File encoding (default: utf-8)",
                required=False,
                default="utf-8"
            ),
        }
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Read file content."""
        return await super().execute(
            action="read",
            filepath=kwargs.get("filepath"),
            encoding=kwargs.get("encoding", "utf-8")
        )


class FileWriterTool(FileManagerTool):
    """Specialized tool for writing files."""
    
    def __init__(self):
        super().__init__()
        self.name = "file_writer"
        self.description = "Write content to files (subset of file_manager)"
        self.args_schema = {
            "filepath": ToolArgument(
                name="filepath",
                type=str,
                description="Path to the file to write"
            ),
            "content": ToolArgument(
                name="content",
                type=str,
                description="Content to write"
            ),
            "encoding": ToolArgument(
                name="encoding",
                type=str,
                description="File encoding (default: utf-8)",
                required=False,
                default="utf-8"
            ),
            "create_dirs": ToolArgument(
                name="create_dirs",
                type=bool,
                description="Create parent directories (default: True)",
                required=False,
                default=True
            ),
        }
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Write content to file."""
        return await super().execute(
            action="write",
            filepath=kwargs.get("filepath"),
            content=kwargs.get("content", ""),
            encoding=kwargs.get("encoding", "utf-8"),
            create_dirs=kwargs.get("create_dirs", True)
        )
