"""
Code Fix Handler - Autonomous Bug Fixing with Aider

Handles code_fix tasks by:
1. Extracting error details (file, line, message)
2. Calling Aider CLI to generate fix
3. Aider commits to branch automatically
4. Creating PR via GitHub API
5. Tracking PR for auto-merge after review

This closes the self-healing loop: error → fix → review → merge → deploy
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseHandler, HandlerResult

logger = logging.getLogger(__name__)

# Aider configuration
AIDER_MODEL = os.getenv("AIDER_MODEL", "deepseek/deepseek-chat")
AIDER_TIMEOUT = int(os.getenv("AIDER_TIMEOUT_SECONDS", "300"))
WORKSPACE_DIR = os.getenv("AIDER_WORKSPACE", "/tmp/juggernaut-fixes")

# GitHub configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEFAULT_REPO = os.getenv("GITHUB_REPO", "")


class CodeFixHandler(BaseHandler):
    """Handler for autonomous code fixing using Aider."""
    
    task_type = "code_fix"
    
    def execute(self, task: Dict[str, Any]) -> HandlerResult:
        """Execute a code fix task using Aider.
        
        Args:
            task: Task dictionary with payload containing:
                - error_message (str): The error message to fix
                - file_path (str): File containing the bug
                - line_number (int, optional): Line number of error
                - traceback (str, optional): Full traceback
                - repo (str, optional): Target repository
        
        Returns:
            HandlerResult with fix details or error information.
        """
        self._execution_logs = []
        task_id = task.get("id")
        payload = task.get("payload", {})
        
        error_message = payload.get("error_message", "")
        file_path = payload.get("file_path", "")
        line_number = payload.get("line_number")
        traceback = payload.get("traceback", "")
        repo = payload.get("repo", DEFAULT_REPO)
        
        self._log(
            "handler.code_fix.starting",
            f"Starting autonomous fix for: {error_message[:100]}",
            task_id=task_id,
        )
        
        # Validate inputs
        if not error_message or not file_path:
            return HandlerResult(
                success=False,
                error="Missing required fields: error_message and file_path",
                logs=self._execution_logs
            )
        
        try:
            # Prepare workspace
            workspace = Path(WORKSPACE_DIR)
            workspace.mkdir(parents=True, exist_ok=True)
            
            repo_name = repo.split("/")[-1]
            repo_dir = workspace / repo_name
            
            # Clone or update repo
            if not repo_dir.exists():
                self._log(
                    "handler.code_fix.cloning",
                    f"Cloning {repo}",
                    task_id=task_id,
                )
                clone_result = subprocess.run(
                    ["git", "clone", f"https://github.com/{repo}.git", str(repo_dir)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if clone_result.returncode != 0:
                    return HandlerResult(
                        success=False,
                        error=f"Failed to clone repo: {clone_result.stderr}",
                        logs=self._execution_logs
                    )
            else:
                # Pull latest
                subprocess.run(
                    ["git", "pull"],
                    cwd=repo_dir,
                    capture_output=True,
                    timeout=30
                )
            
            # Create fix branch
            branch_name = f"fix/{task_id[:8]}-{self._sanitize_filename(error_message[:30])}"
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=repo_dir,
                capture_output=True
            )
            
            self._log(
                "handler.code_fix.branch_created",
                f"Created branch: {branch_name}",
                task_id=task_id,
            )
            
            # Build Aider prompt
            fix_prompt = self._build_fix_prompt(
                error_message, file_path, line_number, traceback
            )
            
            # Call Aider
            self._log(
                "handler.code_fix.calling_aider",
                f"Calling Aider to fix {file_path}",
                task_id=task_id,
            )
            
            aider_result = self._call_aider(
                repo_dir, file_path, fix_prompt, task_id
            )
            
            if not aider_result["success"]:
                return HandlerResult(
                    success=False,
                    error=f"Aider failed: {aider_result.get('error')}",
                    logs=self._execution_logs
                )
            
            # Push branch
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if push_result.returncode != 0:
                return HandlerResult(
                    success=False,
                    error=f"Failed to push branch: {push_result.stderr}",
                    logs=self._execution_logs
                )
            
            self._log(
                "handler.code_fix.pushed",
                f"Pushed branch {branch_name}",
                task_id=task_id,
            )
            
            # Create PR
            pr_result = self._create_pr(
                repo, branch_name, error_message, file_path, task_id
            )
            
            if not pr_result["success"]:
                return HandlerResult(
                    success=False,
                    error=f"Failed to create PR: {pr_result.get('error')}",
                    logs=self._execution_logs
                )
            
            self._log(
                "handler.code_fix.complete",
                f"Fix complete - PR #{pr_result['pr_number']}: {pr_result['pr_url']}",
                task_id=task_id,
            )
            
            return HandlerResult(
                success=True,
                data={
                    "branch": branch_name,
                    "pr_number": pr_result["pr_number"],
                    "pr_url": pr_result["pr_url"],
                    "files_changed": aider_result.get("files_changed", []),
                    "commits": aider_result.get("commits", [])
                },
                logs=self._execution_logs
            )
            
        except subprocess.TimeoutExpired:
            return HandlerResult(
                success=False,
                error="Aider execution timed out",
                logs=self._execution_logs
            )
        except Exception as e:
            logger.exception(f"Code fix handler error: {e}")
            return HandlerResult(
                success=False,
                error=str(e),
                logs=self._execution_logs
            )
    
    def _build_fix_prompt(
        self,
        error_message: str,
        file_path: str,
        line_number: Optional[int],
        traceback: str
    ) -> str:
        """Build prompt for Aider."""
        prompt = f"Fix this error in {file_path}:\n\n"
        prompt += f"Error: {error_message}\n\n"
        
        if line_number:
            prompt += f"Location: Line {line_number}\n\n"
        
        if traceback:
            prompt += f"Traceback:\n{traceback}\n\n"
        
        prompt += "Please fix the bug and commit the changes."
        
        return prompt
    
    def _call_aider(
        self,
        repo_dir: Path,
        file_path: str,
        prompt: str,
        task_id: str
    ) -> Dict[str, Any]:
        """Call Aider CLI to generate fix."""
        try:
            # Write prompt to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            # Run Aider
            cmd = [
                "aider",
                "--yes",  # Auto-confirm
                "--model", AIDER_MODEL,
                "--message-file", prompt_file,
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=AIDER_TIMEOUT,
                env={**os.environ, "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", "")}
            )
            
            # Clean up prompt file
            os.unlink(prompt_file)
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout
                }
            
            # Parse Aider output for files changed
            files_changed = self._parse_aider_output(result.stdout)
            
            return {
                "success": True,
                "files_changed": files_changed,
                "output": result.stdout
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_aider_output(self, output: str) -> list:
        """Extract files changed from Aider output."""
        files = []
        for line in output.split('\n'):
            if 'modified:' in line.lower() or 'created:' in line.lower():
                # Extract filename
                match = re.search(r'[:\s]+([\w/\._-]+\.\w+)', line)
                if match:
                    files.append(match.group(1))
        return files
    
    def _create_pr(
        self,
        repo: str,
        branch: str,
        error_message: str,
        file_path: str,
        task_id: str
    ) -> Dict[str, Any]:
        """Create PR via GitHub API."""
        try:
            import requests
            
            title = f"[AUTO-FIX] {error_message[:80]}"
            body = f"""## Autonomous Bug Fix

**Error:** {error_message}

**File:** `{file_path}`

**Task ID:** `{task_id}`

---

This PR was automatically generated by JUGGERNAUT's self-healing system using Aider.

The fix has been committed to branch `{branch}` and is ready for review.
"""
            
            url = f"https://api.github.com/repos/{repo}/pulls"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {
                "title": title,
                "body": body,
                "head": branch,
                "base": "main"
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code != 201:
                return {
                    "success": False,
                    "error": f"GitHub API error: {response.status_code} - {response.text}"
                }
            
            pr_data = response.json()
            
            return {
                "success": True,
                "pr_number": pr_data["number"],
                "pr_url": pr_data["html_url"]
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _sanitize_filename(self, text: str) -> str:
        """Sanitize text for use in branch name."""
        # Remove special characters, keep alphanumeric and hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
        # Replace spaces with hyphens
        sanitized = re.sub(r'\s+', '-', sanitized)
        # Remove multiple consecutive hyphens
        sanitized = re.sub(r'-+', '-', sanitized)
        return sanitized.lower()
