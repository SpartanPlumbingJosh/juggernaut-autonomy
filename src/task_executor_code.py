"""
Code Task Executor for JUGGERNAUT

Handles autonomous code generation, PR creation, and merging for "code" type tasks.
Integrates CodeGenerator and GitHubClient for end-to-end autonomous development.

Supports multiple repositories via target_repo in task payload.
"""

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_BRANCH_PREFIX = "feature/auto"
MAX_MERGE_WAIT_SECONDS = 300
MERGE_CHECK_INTERVAL_SECONDS = 15

# Supported repositories - add new repos here
SUPPORTED_REPOS = {
    "juggernaut-autonomy": "SpartanPlumbingJosh/juggernaut-autonomy",
    "spartan-hq": "SpartanPlumbingJosh/spartan-hq",
}


@dataclass
class CodeTaskResult:
    """Result of code task execution."""
    success: bool
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    branch: Optional[str] = None
    merged: bool = False
    error: Optional[str] = None
    files_created: Optional[List[str]] = None
    tokens_used: int = 0
    model_used: Optional[str] = None
    target_repo: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "success": self.success,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "branch": self.branch,
            "merged": self.merged,
            "error": self.error,
            "files_created": self.files_created,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
            "target_repo": self.target_repo
        }


class CodeTaskExecutor:
    """
    Executes code-type tasks autonomously.
    
    Workflow:
    1. Parse task description and payload
    2. Generate code using AI (CodeGenerator)
    3. Create branch, commit files, create PR (GitHubClient)
    4. Optionally wait for checks and merge
    
    Supports multiple repositories via target_repo in task payload.
    """
    
    def __init__(
        self,
        log_action_func: Optional[Callable] = None,
        auto_merge: bool = False
    ):
        """
        Initialize code task executor.
        
        Args:
            log_action_func: Function to log actions.
            auto_merge: Whether to automatically merge PRs after creation.
        """
        self.log_action = log_action_func or self._default_log
        self.auto_merge = auto_merge
        self._generator = None
        self._github_clients: Dict[str, Any] = {}
    
    def _default_log(
        self,
        action: str,
        message: str,
        level: str = "info",
        **kwargs: Any
    ) -> None:
        """Default logging function."""
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{action}] {message}")
    
    def _get_generator(self):
        """Lazily initialize code generator."""
        if self._generator is None:
            from src.code_generator import CodeGenerator
            self._generator = CodeGenerator()
        return self._generator
    
    def _get_github(self, repo: Optional[str] = None):
        """
        Get GitHub client for a specific repository.
        
        Args:
            repo: Repository in "owner/repo" format, or short name from SUPPORTED_REPOS.
                  Defaults to juggernaut-autonomy.
        
        Returns:
            Configured GitHubClient instance.
        """
        # Resolve short names to full repo paths
        if repo and repo in SUPPORTED_REPOS:
            repo = SUPPORTED_REPOS[repo]
        elif repo is None:
            repo = SUPPORTED_REPOS.get("juggernaut-autonomy", 
                                       os.getenv("GITHUB_REPO", "SpartanPlumbingJosh/juggernaut-autonomy"))
        
        # Cache clients per repo
        if repo not in self._github_clients:
            from src.github_automation import GitHubClient
            self._github_clients[repo] = GitHubClient(repo=repo)
        
        return self._github_clients[repo]
    
    def _sanitize_branch_name(self, title: str) -> str:
        """Create a valid git branch name from task title."""
        name = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower())
        name = name.strip('-')[:50]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        return f"{DEFAULT_BRANCH_PREFIX}/{name}-{timestamp}"
    
    def _extract_module_name(self, description: str) -> str:
        """Extract a reasonable module name from task description."""
        patterns = [
            r'create\s+(\w+)\s+module',
            r'add\s+(\w+)\s+module',
            r'implement\s+(\w+)',
            r'build\s+(\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description.lower())
            if match:
                return match.group(1)
        
        words = re.findall(r'\w+', description.lower())
        meaningful = [w for w in words if len(w) > 3 and w not in 
                     ('create', 'add', 'implement', 'build', 'the', 'for', 'with')]
        return meaningful[0] if meaningful else "generated_module"
    
    def execute(
        self,
        task_id: str,
        task_title: str,
        task_description: str,
        task_payload: Dict[str, Any]
    ) -> CodeTaskResult:
        """
        Execute a code-type task.
        
        Args:
            task_id: Unique task identifier.
            task_title: Task title.
            task_description: Full task description.
            task_payload: Task payload with parameters including:
                - target_repo: Repository to work on (optional, defaults to juggernaut-autonomy)
                - module_name: Name of module to generate
                - target_path: Path for generated files
                - requirements: List of requirements
                - existing_code: Existing code context
                
        Returns:
            CodeTaskResult with execution outcome.
        """
        # Get target repo from payload
        target_repo = task_payload.get("target_repo") or task_payload.get("repo")
        
        self.log_action(
            "code_task.start",
            f"Starting code task: {task_title}" + (f" (repo: {target_repo})" if target_repo else ""),
            task_id=task_id
        )
        
        try:
            # Parse parameters
            module_name = task_payload.get("module_name") or self._extract_module_name(task_description)
            target_path = task_payload.get("target_path", "src")
            requirements = task_payload.get("requirements", [])
            existing_code = task_payload.get("existing_code")
            
            self.log_action(
                "code_task.params",
                f"Generating module '{module_name}' in {target_path}/",
                task_id=task_id
            )
            
            # Generate code
            generator = self._get_generator()
            generated = generator.generate_module(
                task_description=task_description,
                module_name=module_name,
                requirements=requirements,
                existing_code=existing_code
            )
            
            self.log_action(
                "code_task.generated",
                f"Generated {len(generated.content)} chars using {generated.model_used}",
                task_id=task_id
            )
            
            # Optionally generate tests
            tests = None
            try:
                tests = generator.generate_tests(generated.content, module_name)
            except Exception as test_error:
                self.log_action(
                    "code_task.tests_skipped",
                    f"Skipped test generation: {test_error}",
                    level="warning",
                    task_id=task_id
                )
            
            # Get GitHub client for the target repo
            github = self._get_github(target_repo)
            branch_name = self._sanitize_branch_name(task_title)
            
            github.create_branch(branch_name)
            
            # Commit main module
            module_path = f"{target_path}/{generated.filename}"
            github.commit_file(
                branch=branch_name,
                path=module_path,
                content=generated.content,
                message=f"feat: add {module_name} module\n\nTask: {task_id}\n{task_title}"
            )
            files_created = [module_path]
            
            # Commit tests if generated
            if tests:
                test_path = f"tests/{tests.filename}"
                github.commit_file(
                    branch=branch_name,
                    path=test_path,
                    content=tests.content,
                    message=f"test: add tests for {module_name}"
                )
                files_created.append(test_path)
            
            # Create PR
            pr_body = f"""## Task
{task_title}

## Description
{task_description[:500]}{'...' if len(task_description) > 500 else ''}

## Changes
- Added `{module_path}` - {module_name} module
{'- Added `' + test_path + '` - unit tests' if tests else ''}

## Generated by
JUGGERNAUT Autonomous Engine
- Task ID: `{task_id}`
- Model: `{generated.model_used}`
- Tokens: {generated.tokens_used}
- Target Repo: `{github.repo}`
"""
            
            pr_number = github.create_pr(
                branch=branch_name,
                title=f"[AUTO] {task_title}",
                body=pr_body
            )
            
            pr_url = f"https://github.com/{github.repo}/pull/{pr_number}"
            
            self.log_action(
                "code_task.pr_created",
                f"Created PR #{pr_number}: {pr_url}",
                task_id=task_id
            )
            
            # Auto-merge if enabled
            merged = False
            if self.auto_merge:
                merged = self._wait_and_merge(github, pr_number, task_id)
            
            return CodeTaskResult(
                success=True,
                pr_number=pr_number,
                pr_url=pr_url,
                branch=branch_name,
                merged=merged,
                files_created=files_created,
                tokens_used=generated.tokens_used + (tests.tokens_used if tests else 0),
                model_used=generated.model_used,
                target_repo=github.repo
            )
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.log_action(
                "code_task.failed",
                f"Code task failed: {error_msg}",
                level="error",
                task_id=task_id
            )
            return CodeTaskResult(success=False, error=error_msg, target_repo=target_repo)
    
    def _wait_and_merge(
        self,
        github,
        pr_number: int,
        task_id: str
    ) -> bool:
        """Wait for PR checks and merge if possible."""
        waited = 0
        while waited < MAX_MERGE_WAIT_SECONDS:
            try:
                status = github.get_pr_status(pr_number)
                
                if status.mergeable is True and status.checks_passed:
                    github.merge_pr(pr_number, method="squash")
                    self.log_action(
                        "code_task.merged",
                        f"PR #{pr_number} merged successfully",
                        task_id=task_id
                    )
                    return True
                
                if status.mergeable is False:
                    return False
                
            except Exception:
                pass
            
            time.sleep(MERGE_CHECK_INTERVAL_SECONDS)
            waited += MERGE_CHECK_INTERVAL_SECONDS
        
        return False


# Module-level executor instance
_executor: Optional[CodeTaskExecutor] = None


def get_executor(
    log_action_func: Optional[Callable] = None,
    auto_merge: bool = False
) -> CodeTaskExecutor:
    """Get or create the code task executor instance."""
    global _executor
    if _executor is None:
        _executor = CodeTaskExecutor(
            log_action_func=log_action_func,
            auto_merge=auto_merge
        )
    return _executor


def execute_code_task(
    task_id: str,
    task_title: str,
    task_description: str,
    task_payload: Dict[str, Any],
    log_action_func: Optional[Callable] = None,
    auto_merge: bool = False
) -> Dict[str, Any]:
    """
    Convenience function to execute a code task.
    
    Args:
        task_id: Task identifier.
        task_title: Task title.
        task_description: Task description.
        task_payload: Task payload (can include target_repo).
        log_action_func: Optional logging function.
        auto_merge: Whether to auto-merge PRs.
        
    Returns:
        Result dictionary.
    """
    executor = get_executor(log_action_func, auto_merge)
    result = executor.execute(task_id, task_title, task_description, task_payload)
    return result.to_dict()


__all__ = [
    "CodeTaskExecutor",
    "CodeTaskResult",
    "SUPPORTED_REPOS",
    "get_executor",
    "execute_code_task",
]
