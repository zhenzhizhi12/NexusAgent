"""
Shell Executor Tool

Provides asynchronous execution of system commands for agents.
Supports both subprocess.run (for simple commands) and asyncio subprocess
(for long-running or complex commands).
"""

import asyncio
import logging
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

from coordinator.core.tool import BaseTool, ToolExecutionResult, ToolArgument


logger = logging.getLogger("ShellExecutorTool")


class ShellExecutorTool(BaseTool):
    """Execute system commands with asyncio support.
    
    Features:
    - Async subprocess execution for non-blocking operations
    - Cross-platform command handling (Windows/Unix)
    - Environment variable support
    - Working directory control
    - Output capture (stdout/stderr)
    - Exit code tracking
    - Timeout management
    """
    
    def __init__(self):
        """Initialize the shell executor tool."""
        super().__init__(
            name="shell_executor",
            description="Execute system commands asynchronously. Supports Windows and Unix commands.",
            args_schema={
                "command": ToolArgument(
                    name="command",
                    type=str,
                    description="Command string to execute (e.g., 'ls -la' or 'dir /B')"
                ),
                "working_dir": ToolArgument(
                    name="working_dir",
                    type=str,
                    description="Working directory for command execution",
                    required=False,
                    default=None
                ),
                "timeout": ToolArgument(
                    name="timeout",
                    type=int,
                    description="Timeout in seconds (default: 300)",
                    required=False,
                    default=300
                ),
                "shell": ToolArgument(
                    name="shell",
                    type=bool,
                    description="Run command through shell (default: True on Windows)",
                    required=False,
                    default=None
                ),
                "env": ToolArgument(
                    name="env",
                    type=dict,
                    description="Additional environment variables",
                    required=False,
                    default=None
                ),
            }
        )
    
    async def execute(self, **kwargs) -> ToolExecutionResult:
        """Execute a shell command."""
        command = kwargs.get("command")
        working_dir = kwargs.get("working_dir")
        timeout = kwargs.get("timeout", 300)
        shell = kwargs.get("shell", None)
        env = kwargs.get("env", None)
        
        metadata = {
            "command": command,
            "working_dir": working_dir,
            "timeout": timeout,
        }
        
        try:
            # Auto-detect shell parameter
            if shell is None:
                shell = True  # Default to True for better compatibility
            
            # Prepare working directory
            cwd = Path(working_dir) if working_dir else None
            if cwd and not cwd.exists():
                return ToolExecutionResult(
                    status="error",
                    output=None,
                    error=f"Working directory does not exist: {working_dir}"
                )
            
            # Prepare environment
            import os
            cmd_env = os.environ.copy()
            if env:
                cmd_env.update(env)
            
            logger.info(f"[ShellExecutor] Executing: {command} in {working_dir or 'current dir'}")
            
            # Execute command
            if not command:
                return ToolExecutionResult(
                    status="error",
                    output=None,
                    error="Command is required",
                    metadata=metadata
                )
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolExecutionResult(
                    status="failure",
                    output=None,
                    error=f"Command timed out after {timeout} seconds",
                    metadata=metadata
                )
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='ignore') if stdout else ""
            stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else ""
            
            # Handle exit code
            exit_code = process.returncode
            success = exit_code == 0
            
            metadata.update({
                "exit_code": exit_code,
                "stdout_lines": len(stdout_text.splitlines()),
                "stderr_lines": len(stderr_text.splitlines()),
            })
            
            if success:
                logger.info(f"[ShellExecutor] Command succeeded (exit code: {exit_code})")
                return ToolExecutionResult(
                    status="success",
                    output={
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "exit_code": exit_code,
                    },
                    metadata=metadata
                )
            else:
                logger.warning(f"[ShellExecutor] Command failed (exit code: {exit_code})")
                return ToolExecutionResult(
                    status="failure",
                    output={
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "exit_code": exit_code,
                    },
                    error=f"Command failed with exit code {exit_code}",
                    metadata=metadata
                )
            
        except Exception as e:
            logger.error(f"[ShellExecutor] Execution error: {e}", exc_info=True)
            return ToolExecutionResult(
                status="error",
                output=None,
                error=str(e),
                metadata=metadata
            )
    
    async def execute_script(
        self,
        script_path: str,
        script_args: Optional[list] = None,
        working_dir: Optional[str] = None,
        timeout: int = 600
    ) -> ToolExecutionResult:
        """Execute a script file (Python, PowerShell, Bash, etc.).
        
        Args:
            script_path: Path to the script file
            script_args: Arguments to pass to the script
            working_dir: Working directory
            timeout: Execution timeout
            
        Returns:
            ToolExecutionResult
        """
        script_file = Path(script_path)
        
        if not script_file.exists():
            return ToolExecutionResult(
                status="error",
                output=None,
                error=f"Script file not found: {script_path}"
            )
        
        # Determine interpreter based on extension
        interpreter = None
        extension = script_file.suffix.lower()
        
        if extension in ['.py']:
            interpreter = 'python'
        elif extension in ['.ps1']:
            interpreter = 'powershell'
        elif extension in ['.sh', '.bash']:
            interpreter = 'bash'
        elif extension in ['.bat', '.cmd']:
            interpreter = 'cmd'
        
        if interpreter:
            args = [interpreter, str(script_file)]
            if script_args:
                args.extend(script_args)
            command = ' '.join(shlex.quote(arg) for arg in args)
        else:
            # Try to execute directly
            command = str(script_file)
            if script_args:
                command += ' ' + ' '.join(shlex.quote(arg) for arg in script_args)
        
        return await self.execute(
            command=command,
            working_dir=working_dir,
            timeout=timeout
        )


class CommandExecutorTool(ShellExecutorTool):
    """Alias for ShellExecutorTool for backward compatibility."""
    
    def __init__(self):
        super().__init__()
        self.name = "command_executor"
        self.description = "Execute system commands (alias for shell_executor)"
