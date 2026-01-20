"""
JUGGERNAUT GitHub Automation Module

Enables the engine to write code, create branches, submit PRs, and merge changes
autonomously. Uses OpenRouter smart router for AI-powered code generation.

This is the key capability that allows JUGGERNAUT to extend itself.
"""

import base64
import json
import logging
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

# Import brain for AI-powered code generation
from core.brain import BrainService, BrainError

logger = logging.getLogger(__name__)

# Configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy")
DEFAULT_BRANCH = "main"

# Code generation prompts
CODE_GENERATION_SYSTEM_PROMPT = """You are an expert Python developer for the JUGGERNAUT autonomy system.
You write clean, production-ready code following these standards:

MANDATORY REQUIREMENTS:
- Type hints on EVERY function parameter and return value
- Docstrings on EVERY function and class
- No bare except: - catch specific exceptions
- No print() - use logging module
- No magic numbers - use named constants
- SQL must be parameterized (no string formatting)
- Imports grouped: stdlib, third-party, local

CODE STYLE:
- Clear, descriptive variable names
- Functions should do one thing well
- Maximum function length: 50 lines
- Use dataclasses for data structures
- Prefer composition over inheritance

When generating code, output ONLY the code - no explanations, no markdown backticks."""

PR_DESCRIPTION_PROMPT = """Generate a clear, concise PR description for the following changes.
Include:
- What was changed
- Why it was changed
- Any testing notes

Output format:
## Summary
[1-2 sentence summary]

## Changes
- [bullet points of changes]

## Testing
- [how to test]
"""


class GitHubError(Exception):
    """Base exception for GitHub operations."""
    pass


class CodeGenerationError(Exception):
    """Error generating code."""
    pass


@dataclass
class GitHubFile:
    """Represents a file in the repository."""
    path: str
    content: str
    sha: Optional[str] = None
    encoding: str = "utf-8"


@dataclass
class PullRequest:
    """Represents a GitHub pull request."""
    number: int
    title: str
    body: str
    head: str
    base: str
    state: str
    html_url: str
    mergeable: Optional[bool] = None


@dataclass
class CodeGenerationResult:
    """Result of code generation."""
    success: bool
    code: str = ""
    error: str = ""
    model_used: str = ""
    tokens_used: int = 0
    cost_cents: float = 0.0


class GitHubClient:
    """
    Client for GitHub API operations.
    
    Handles all GitHub interactions including file operations,
    branch management, and pull request workflows.
    """
    
    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None
    ):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub API token. Defaults to GITHUB_TOKEN env var.
            repo: Repository in owner/name format. Defaults to GITHUB_REPO env var.
        """
        self.token = token or GITHUB_TOKEN
        self.repo = repo or GITHUB_REPO
        
        if not self.token:
            raise GitHubError("GITHUB_TOKEN not configured")
        if not self.repo:
            raise GitHubError("GITHUB_REPO not configured")
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a GitHub API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint (without base URL).
            data: Request body data.
            headers: Additional headers.
            
        Returns:
            Response JSON as dict.
            
        Raises:
            GitHubError: If request fails.
        """
        url = f"{GITHUB_API_BASE}{endpoint}"
        
        request_headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "Juggernaut-Autonomy"
        }
        if headers:
            request_headers.update(headers)
        
        body = None
        if data:
            body = json.dumps(data).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                response_body = response.read().decode("utf-8")
                if response_body:
                    return json.loads(response_body)
                return {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            logger.error(f"GitHub API error: {e.code} - {error_body}")
            raise GitHubError(f"GitHub API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            logger.error(f"GitHub connection error: {e}")
            raise GitHubError(f"Connection error: {e}")
    
    def get_branch_sha(self, branch: str = DEFAULT_BRANCH) -> str:
        """
        Get the SHA of a branch's HEAD commit.
        
        Args:
            branch: Branch name.
            
        Returns:
            SHA string.
        """
        result = self._request("GET", f"/repos/{self.repo}/git/ref/heads/{branch}")
        return result["object"]["sha"]
    
    def create_branch(self, branch_name: str, from_branch: str = DEFAULT_BRANCH) -> str:
        """
        Create a new branch.
        
        Args:
            branch_name: Name for new branch.
            from_branch: Branch to create from.
            
        Returns:
            SHA of the new branch.
        """
        sha = self.get_branch_sha(from_branch)
        
        result = self._request(
            "POST",
            f"/repos/{self.repo}/git/refs",
            {"ref": f"refs/heads/{branch_name}", "sha": sha}
        )
        
        logger.info(f"Created branch {branch_name} from {from_branch}")
        return result["object"]["sha"]
    
    def get_file(self, path: str, branch: str = DEFAULT_BRANCH) -> Optional[GitHubFile]:
        """
        Get a file from the repository.
        
        Args:
            path: File path.
            branch: Branch to get file from.
            
        Returns:
            GitHubFile object or None if not found.
        """
        try:
            result = self._request(
                "GET",
                f"/repos/{self.repo}/contents/{path}?ref={branch}"
            )
            
            content = base64.b64decode(result["content"]).decode("utf-8")
            return GitHubFile(
                path=path,
                content=content,
                sha=result["sha"]
            )
        except GitHubError as e:
            if "404" in str(e):
                return None
            raise
    
    def create_or_update_file(
        self,
        path: str,
        content: str,
        message: str,
        branch: str
    ) -> Dict[str, Any]:
        """
        Create or update a file in the repository.
        
        Args:
            path: File path.
            content: File content.
            message: Commit message.
            branch: Branch to commit to.
            
        Returns:
            API response with commit info.
        """
        # Check if file exists to get SHA
        existing = self.get_file(path, branch)
        
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        
        if existing:
            data["sha"] = existing.sha
        
        result = self._request(
            "PUT",
            f"/repos/{self.repo}/contents/{path}",
            data
        )
        
        action = "Updated" if existing else "Created"
        logger.info(f"{action} file {path} on branch {branch}")
        return result
    
    def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str = DEFAULT_BRANCH
    ) -> PullRequest:
        """
        Create a pull request.
        
        Args:
            title: PR title.
            body: PR description.
            head: Source branch.
            base: Target branch.
            
        Returns:
            PullRequest object.
        """
        result = self._request(
            "POST",
            f"/repos/{self.repo}/pulls",
            {
                "title": title,
                "body": body,
                "head": head,
                "base": base
            }
        )
        
        pr = PullRequest(
            number=result["number"],
            title=result["title"],
            body=result["body"],
            head=head,
            base=base,
            state=result["state"],
            html_url=result["html_url"],
            mergeable=result.get("mergeable")
        )
        
        logger.info(f"Created PR #{pr.number}: {pr.title}")
        return pr
    
    def merge_pull_request(
        self,
        pr_number: int,
        merge_method: str = "squash"
    ) -> Dict[str, Any]:
        """
        Merge a pull request.
        
        Args:
            pr_number: PR number.
            merge_method: Merge method (merge, squash, rebase).
            
        Returns:
            API response with merge info.
        """
        result = self._request(
            "PUT",
            f"/repos/{self.repo}/pulls/{pr_number}/merge",
            {"merge_method": merge_method}
        )
        
        logger.info(f"Merged PR #{pr_number} via {merge_method}")
        return result
    
    def get_pull_request(self, pr_number: int) -> PullRequest:
        """
        Get pull request details.
        
        Args:
            pr_number: PR number.
            
        Returns:
            PullRequest object.
        """
        result = self._request("GET", f"/repos/{self.repo}/pulls/{pr_number}")
        
        return PullRequest(
            number=result["number"],
            title=result["title"],
            body=result["body"] or "",
            head=result["head"]["ref"],
            base=result["base"]["ref"],
            state=result["state"],
            html_url=result["html_url"],
            mergeable=result.get("mergeable")
        )


class CodeGenerator:
    """
    AI-powered code generation using OpenRouter smart router.
    
    Uses the brain module to generate code based on task descriptions,
    following JUGGERNAUT code standards.
    """
    
    def __init__(self, brain: Optional[BrainService] = None):
        """
        Initialize code generator.
        
        Args:
            brain: BrainService instance. Creates new one if None.
        """
        self.brain = brain or BrainService()
    
    def generate_code(
        self,
        task_description: str,
        file_path: str,
        existing_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> CodeGenerationResult:
        """
        Generate code for a task.
        
        Args:
            task_description: What the code should do.
            file_path: Target file path (helps with imports).
            existing_code: Existing code to modify/extend.
            context: Additional context (related files, etc).
            
        Returns:
            CodeGenerationResult with generated code.
        """
        prompt_parts = [
            f"Task: {task_description}",
            f"File: {file_path}",
        ]
        
        if existing_code:
            prompt_parts.append(f"\nExisting code to modify:\n```python\n{existing_code}\n```")
        
        if context:
            prompt_parts.append(f"\nContext: {json.dumps(context, indent=2)}")
        
        prompt_parts.append("\nGenerate the complete Python code:")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            result = self.brain.consult(
                prompt,
                system_prompt=CODE_GENERATION_SYSTEM_PROMPT,
                include_memories=False  # Don't need memories for code gen
            )
            
            code = result["response"]
            
            # Clean up response - remove markdown if present
            code = self._clean_code(code)
            
            # Validate basic syntax
            try:
                compile(code, file_path, "exec")
            except SyntaxError as e:
                return CodeGenerationResult(
                    success=False,
                    error=f"Generated code has syntax error: {e}",
                    code=code,
                    model_used=result.get("model", "unknown")
                )
            
            return CodeGenerationResult(
                success=True,
                code=code,
                model_used=result.get("model", "unknown"),
                tokens_used=result.get("input_tokens", 0) + result.get("output_tokens", 0),
                cost_cents=result.get("cost_cents", 0.0)
            )
            
        except BrainError as e:
            logger.error(f"Code generation failed: {e}")
            return CodeGenerationResult(
                success=False,
                error=str(e)
            )
    
    def generate_pr_description(
        self,
        title: str,
        files_changed: List[str],
        task_description: str
    ) -> str:
        """
        Generate a PR description.
        
        Args:
            title: PR title.
            files_changed: List of changed file paths.
            task_description: Original task description.
            
        Returns:
            Formatted PR description.
        """
        prompt = f"""
PR Title: {title}
Files Changed: {', '.join(files_changed)}
Original Task: {task_description}

{PR_DESCRIPTION_PROMPT}
"""
        
        try:
            result = self.brain.consult(
                prompt,
                include_memories=False
            )
            return result["response"]
        except BrainError:
            # Fallback to simple description
            return f"""## Summary
{task_description}

## Changes
- Modified: {', '.join(files_changed)}

## Testing
- Verify code compiles
- Run existing tests
"""
    
    def _clean_code(self, code: str) -> str:
        """
        Clean generated code - remove markdown fences, etc.
        
        Args:
            code: Raw generated code.
            
        Returns:
            Cleaned code.
        """
        # Remove markdown code fences
        code = re.sub(r'^```python\s*\n', '', code)
        code = re.sub(r'^```\s*\n', '', code)
        code = re.sub(r'\n```\s*$', '', code)
        code = re.sub(r'^```\s*$', '', code, flags=re.MULTILINE)
        
        return code.strip()


class GitHubAutomation:
    """
    High-level GitHub automation for code changes.
    
    Combines code generation with GitHub operations to enable
    end-to-end autonomous code changes.
    """
    
    def __init__(
        self,
        github: Optional[GitHubClient] = None,
        code_gen: Optional[CodeGenerator] = None
    ):
        """
        Initialize GitHub automation.
        
        Args:
            github: GitHubClient instance.
            code_gen: CodeGenerator instance.
        """
        self.github = github or GitHubClient()
        self.code_gen = code_gen or CodeGenerator()
    
    def create_feature(
        self,
        task_id: str,
        task_description: str,
        target_files: List[str],
        auto_merge: bool = False
    ) -> Dict[str, Any]:
        """
        Create a complete feature: branch, code, PR.
        
        Args:
            task_id: Task ID for branch naming.
            task_description: What to implement.
            target_files: Files to create/modify.
            auto_merge: Whether to auto-merge if PR is clean.
            
        Returns:
            Dict with branch, files, pr_number, pr_url, merged status.
        """
        # Generate unique branch name
        branch_name = f"feature/{task_id[:8]}-{uuid4().hex[:4]}"
        
        result = {
            "branch": branch_name,
            "files": [],
            "pr_number": None,
            "pr_url": None,
            "merged": False,
            "errors": []
        }
        
        try:
            # Create branch
            self.github.create_branch(branch_name)
            
            # Generate and commit code for each file
            for file_path in target_files:
                # Get existing content if file exists
                existing = self.github.get_file(file_path, DEFAULT_BRANCH)
                existing_code = existing.content if existing else None
                
                # Generate code
                gen_result = self.code_gen.generate_code(
                    task_description,
                    file_path,
                    existing_code=existing_code
                )
                
                if not gen_result.success:
                    result["errors"].append(f"{file_path}: {gen_result.error}")
                    continue
                
                # Commit file
                action = "Update" if existing else "Add"
                self.github.create_or_update_file(
                    file_path,
                    gen_result.code,
                    f"{action} {file_path}: {task_description[:50]}",
                    branch_name
                )
                
                result["files"].append({
                    "path": file_path,
                    "action": action.lower(),
                    "tokens_used": gen_result.tokens_used,
                    "cost_cents": gen_result.cost_cents
                })
            
            # Only create PR if we have files
            if result["files"]:
                # Generate PR description
                pr_body = self.code_gen.generate_pr_description(
                    task_description[:80],
                    [f["path"] for f in result["files"]],
                    task_description
                )
                
                # Create PR
                pr = self.github.create_pull_request(
                    title=task_description[:80],
                    body=pr_body,
                    head=branch_name
                )
                
                result["pr_number"] = pr.number
                result["pr_url"] = pr.html_url
                
                # Auto-merge if requested and PR is mergeable
                if auto_merge:
                    try:
                        self.github.merge_pull_request(pr.number)
                        result["merged"] = True
                    except GitHubError as e:
                        result["errors"].append(f"Auto-merge failed: {e}")
            
            return result
            
        except GitHubError as e:
            result["errors"].append(str(e))
            return result
    
    def add_file_to_branch(
        self,
        branch: str,
        file_path: str,
        task_description: str
    ) -> Dict[str, Any]:
        """
        Add a single file to an existing branch.
        
        Args:
            branch: Target branch.
            file_path: File to create/modify.
            task_description: What to implement.
            
        Returns:
            Dict with success, file info, errors.
        """
        result = {
            "success": False,
            "file_path": file_path,
            "errors": []
        }
        
        try:
            existing = self.github.get_file(file_path, branch)
            existing_code = existing.content if existing else None
            
            gen_result = self.code_gen.generate_code(
                task_description,
                file_path,
                existing_code=existing_code
            )
            
            if not gen_result.success:
                result["errors"].append(gen_result.error)
                return result
            
            action = "Update" if existing else "Add"
            self.github.create_or_update_file(
                file_path,
                gen_result.code,
                f"{action} {file_path}: {task_description[:50]}",
                branch
            )
            
            result["success"] = True
            result["action"] = action.lower()
            result["tokens_used"] = gen_result.tokens_used
            result["cost_cents"] = gen_result.cost_cents
            
            return result
            
        except (GitHubError, CodeGenerationError) as e:
            result["errors"].append(str(e))
            return result


# Module-level convenience functions

def create_feature(
    task_id: str,
    task_description: str,
    target_files: List[str],
    auto_merge: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to create a feature.
    
    Args:
        task_id: Task ID for naming.
        task_description: What to implement.
        target_files: Files to create/modify.
        auto_merge: Auto-merge if clean.
        
    Returns:
        Feature creation result.
    """
    automation = GitHubAutomation()
    return automation.create_feature(task_id, task_description, target_files, auto_merge)


def generate_code(
    task_description: str,
    file_path: str,
    existing_code: Optional[str] = None
) -> CodeGenerationResult:
    """
    Convenience function to generate code.
    
    Args:
        task_description: What the code should do.
        file_path: Target file path.
        existing_code: Code to modify.
        
    Returns:
        Code generation result.
    """
    generator = CodeGenerator()
    return generator.generate_code(task_description, file_path, existing_code)


__all__ = [
    "GitHubClient",
    "GitHubError",
    "GitHubFile",
    "PullRequest",
    "CodeGenerator",
    "CodeGenerationResult",
    "CodeGenerationError",
    "GitHubAutomation",
    "create_feature",
    "generate_code",
]
