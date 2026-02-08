"""
JUGGERNAUT Aider Integration

Wraps the Aider CLI for context-aware code generation.
Aider clones the repo, reads existing code, makes targeted edits,
and commits directly — replacing the blind CodeGenerator.

Usage:
    executor = AiderExecutor()
    result = executor.run(
        repo="owner/repo",
        task_description="Fix the retry logic in core/failover.py",
        target_files=["core/failover.py"],
    )
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Aider CLI defaults
AIDER_MODEL = os.getenv("AIDER_MODEL", "openai/gpt-4o-mini")
AIDER_EDIT_FORMAT = os.getenv("AIDER_EDIT_FORMAT", "diff")
AIDER_TIMEOUT_SECONDS = int(os.getenv("AIDER_TIMEOUT_SECONDS", "300"))
AIDER_MAX_RETRIES = int(os.getenv("AIDER_MAX_RETRIES", "2"))

# Git config
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "JUGGERNAUT Engine")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "engine@juggernaut.dev")

# Workspace for cloned repos
WORKSPACE_DIR = os.getenv("AIDER_WORKSPACE", "/tmp/juggernaut-repos")


@dataclass
class AiderResult:
    """Result of an Aider execution."""

    success: bool
    files_changed: List[str] = field(default_factory=list)
    commit_hashes: List[str] = field(default_factory=list)
    branch: Optional[str] = None
    aider_output: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "files_changed": self.files_changed,
            "commit_hashes": self.commit_hashes,
            "branch": self.branch,
            "aider_output": self.aider_output[:2000],
            "error": self.error,
            "duration_seconds": round(self.duration_seconds, 1),
            "model_used": self.model_used,
        }


class AiderExecutor:
    """
    Executes code tasks using Aider CLI.

    Workflow:
    1. Clone target repo (or reuse cached clone)
    2. Create feature branch
    3. Run Aider with task description + relevant files
    4. Aider reads context, makes edits, auto-commits
    5. Push branch and return results for PR creation
    """

    def __init__(
        self,
        log_action: Optional[Callable] = None,
        workspace_dir: str = WORKSPACE_DIR,
    ):
        self.log = log_action or self._default_log
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def _default_log(
        self, action: str, message: str, level: str = "info", **kwargs: Any
    ) -> None:
        log_fn = getattr(logger, level, logger.info)
        log_fn("[%s] %s", action, message)

    def _repo_dir(self, repo: str) -> Path:
        """Get the local directory for a cloned repo."""
        safe_name = repo.replace("/", "--")
        return self.workspace_dir / safe_name

    def _ensure_clone(self, repo: str) -> Path:
        """Clone or update the repository."""
        repo_dir = self._repo_dir(repo)
        token = (os.getenv("GITHUB_TOKEN") or "").strip()

        if not token:
            raise RuntimeError("GITHUB_TOKEN is required for Aider repo operations")

        clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"

        if repo_dir.exists() and (repo_dir / ".git").exists():
            # Fetch latest
            self.log("aider.git", f"Fetching latest for {repo}")
            self._run_git(["fetch", "--all", "--prune"], cwd=repo_dir)
            default_branch = self._get_default_branch(repo_dir)
            self._run_git(["checkout", default_branch], cwd=repo_dir)
            self._run_git(["reset", "--hard", f"origin/{default_branch}"], cwd=repo_dir)
        else:
            # Fresh clone
            self.log("aider.git", f"Cloning {repo}")
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            self._run_git(
                ["clone", "--depth", "50", clone_url, str(repo_dir)],
                cwd=self.workspace_dir,
            )

        # Configure git identity
        self._run_git(["config", "user.name", GIT_USER_NAME], cwd=repo_dir)
        self._run_git(["config", "user.email", GIT_USER_EMAIL], cwd=repo_dir)

        return repo_dir

    def _get_default_branch(self, repo_dir: Path) -> str:
        """Detect the default branch (main or master)."""
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            ref = result.stdout.strip()
            return ref.split("/")[-1]
        return "main"

    def _run_git(self, args: List[str], cwd: Path) -> subprocess.CompletedProcess:
        """Run a git command."""
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("git %s failed: %s", " ".join(args[:3]), result.stderr[:300])
        return result

    def _create_branch(self, repo_dir: Path, task_title: str) -> str:
        """Create a feature branch from the task title."""
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", task_title.lower()).strip("-")[:50]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        branch = f"feature/auto/{slug}-{ts}"
        self._run_git(["checkout", "-b", branch], cwd=repo_dir)
        return branch

    def _get_changed_files(self, repo_dir: Path, base_branch: str) -> List[str]:
        """Get list of files changed since branching."""
        result = self._run_git(
            ["diff", "--name-only", f"origin/{base_branch}...HEAD"],
            cwd=repo_dir,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split("\n") if f]
        return []

    def _get_commit_hashes(self, repo_dir: Path, base_branch: str) -> List[str]:
        """Get commit hashes since branching."""
        result = self._run_git(
            ["log", "--format=%H", f"origin/{base_branch}..HEAD"],
            cwd=repo_dir,
        )
        if result.returncode == 0:
            return [h for h in result.stdout.strip().split("\n") if h]
        return []

    def _build_aider_env(self) -> Dict[str, str]:
        """Build environment variables for Aider subprocess."""
        env = os.environ.copy()

        # Aider uses these env vars for LLM access
        # If LiteLLM proxy is configured, point Aider at it
        llm_base = (os.getenv("LLM_API_BASE") or "").strip()
        llm_key = (os.getenv("LLM_API_KEY") or "").strip()

        if llm_base:
            # LiteLLM proxy mode — set as OpenAI-compatible endpoint
            env["OPENAI_API_BASE"] = llm_base
            env["OPENAI_API_KEY"] = llm_key or "not-needed"
        else:
            # Direct provider keys
            openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
            openrouter_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()

            if openai_key:
                env["OPENAI_API_KEY"] = openai_key
            if openrouter_key and not openai_key:
                # Fall back to OpenRouter via OpenAI-compatible endpoint
                env["OPENAI_API_BASE"] = "https://openrouter.ai/api/v1"
                env["OPENAI_API_KEY"] = openrouter_key

        return env

    def run(
        self,
        repo: str,
        task_description: str,
        task_id: str = "",
        task_title: str = "",
        target_files: Optional[List[str]] = None,
        read_only_files: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> AiderResult:
        """
        Execute a code task using Aider.

        Args:
            repo: Repository in "owner/repo" format.
            task_description: Full task description for Aider.
            task_id: Task ID for logging.
            task_title: Task title (used for branch name).
            target_files: Files Aider should edit (added to chat).
            read_only_files: Files Aider should read for context only.
            model: Override model (default: AIDER_MODEL env var).

        Returns:
            AiderResult with execution outcome.
        """
        start = time.time()
        model = model or AIDER_MODEL

        self.log(
            "aider.start",
            f"Running Aider on {repo}: {task_title or task_description[:80]}",
            task_id=task_id,
        )

        try:
            # 1. Clone / update repo
            repo_dir = self._ensure_clone(repo)
            base_branch = self._get_default_branch(repo_dir)

            # 2. Create feature branch
            branch = self._create_branch(repo_dir, task_title or task_description[:50])

            # 3. Build Aider command
            cmd = [
                "aider",
                "--model", model,
                "--edit-format", AIDER_EDIT_FORMAT,
                "--yes-always",
                "--no-auto-lint",
                "--no-auto-test",
                "--no-suggest-shell-commands",
                "--no-pretty",
                "--no-stream",
                "--message", task_description,
            ]

            # Add target files (Aider will read + edit these)
            if target_files:
                for f in target_files:
                    cmd.extend(["--file", f])

            # Add read-only context files
            if read_only_files:
                for f in read_only_files:
                    cmd.extend(["--read", f])

            # 4. Run Aider
            self.log(
                "aider.exec",
                f"Executing: aider --model {model} on branch {branch}",
                task_id=task_id,
            )

            env = self._build_aider_env()
            result = subprocess.run(
                cmd,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=AIDER_TIMEOUT_SECONDS,
                env=env,
            )

            aider_output = result.stdout + ("\n" + result.stderr if result.stderr else "")

            # 5. Check what Aider did
            files_changed = self._get_changed_files(repo_dir, base_branch)
            commit_hashes = self._get_commit_hashes(repo_dir, base_branch)

            if not files_changed and not commit_hashes:
                # Aider ran but made no changes
                self.log(
                    "aider.no_changes",
                    f"Aider completed but made no changes. Exit code: {result.returncode}",
                    level="warning",
                    task_id=task_id,
                )
                return AiderResult(
                    success=False,
                    branch=branch,
                    aider_output=aider_output,
                    error="Aider made no changes to the codebase",
                    duration_seconds=time.time() - start,
                    model_used=model,
                )

            # 6. Push the branch
            push_result = self._run_git(["push", "-u", "origin", branch], cwd=repo_dir)
            if push_result.returncode != 0:
                return AiderResult(
                    success=False,
                    files_changed=files_changed,
                    commit_hashes=commit_hashes,
                    branch=branch,
                    aider_output=aider_output,
                    error=f"Git push failed: {push_result.stderr[:300]}",
                    duration_seconds=time.time() - start,
                    model_used=model,
                )

            self.log(
                "aider.complete",
                f"Aider modified {len(files_changed)} files in {len(commit_hashes)} commits on {branch}",
                task_id=task_id,
            )

            return AiderResult(
                success=True,
                files_changed=files_changed,
                commit_hashes=commit_hashes,
                branch=branch,
                aider_output=aider_output,
                duration_seconds=time.time() - start,
                model_used=model,
            )

        except subprocess.TimeoutExpired:
            return AiderResult(
                success=False,
                error=f"Aider timed out after {AIDER_TIMEOUT_SECONDS}s",
                duration_seconds=time.time() - start,
                model_used=model,
            )
        except Exception as e:
            self.log(
                "aider.error",
                f"Aider execution failed: {type(e).__name__}: {e}",
                level="error",
                task_id=task_id,
            )
            return AiderResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                duration_seconds=time.time() - start,
                model_used=model,
            )

    def run_with_review_feedback(
        self,
        repo: str,
        branch: str,
        review_comments: str,
        task_id: str = "",
        target_files: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> AiderResult:
        """
        Re-run Aider on an existing branch with code review feedback.

        This is the iteration loop: CodeRabbit reviews → feedback → Aider fixes.

        Args:
            repo: Repository in "owner/repo" format.
            branch: Existing feature branch to check out.
            review_comments: Code review feedback to address.
            task_id: Task ID for logging.
            target_files: Files to focus on (optional).
            model: Override model.

        Returns:
            AiderResult with iteration outcome.
        """
        start = time.time()
        model = model or AIDER_MODEL

        self.log(
            "aider.review_iteration",
            f"Iterating on review feedback for {branch}",
            task_id=task_id,
        )

        try:
            repo_dir = self._ensure_clone(repo)
            base_branch = self._get_default_branch(repo_dir)

            # Checkout the existing feature branch
            self._run_git(["fetch", "origin", branch], cwd=repo_dir)
            self._run_git(["checkout", branch], cwd=repo_dir)
            self._run_git(["pull", "origin", branch], cwd=repo_dir)

            # Build prompt incorporating review feedback
            prompt = (
                "Code review feedback was received on this branch. "
                "Please address the following review comments:\n\n"
                f"{review_comments}\n\n"
                "Make the minimal necessary changes to address this feedback."
            )

            cmd = [
                "aider",
                "--model", model,
                "--edit-format", AIDER_EDIT_FORMAT,
                "--yes-always",
                "--no-auto-lint",
                "--no-auto-test",
                "--no-suggest-shell-commands",
                "--no-pretty",
                "--no-stream",
                "--message", prompt,
            ]

            if target_files:
                for f in target_files:
                    cmd.extend(["--file", f])

            env = self._build_aider_env()
            result = subprocess.run(
                cmd,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=AIDER_TIMEOUT_SECONDS,
                env=env,
            )

            aider_output = result.stdout + ("\n" + result.stderr if result.stderr else "")
            files_changed = self._get_changed_files(repo_dir, base_branch)
            commit_hashes = self._get_commit_hashes(repo_dir, base_branch)

            # Push updates
            push_result = self._run_git(["push", "origin", branch], cwd=repo_dir)
            if push_result.returncode != 0:
                return AiderResult(
                    success=False,
                    files_changed=files_changed,
                    branch=branch,
                    aider_output=aider_output,
                    error=f"Git push failed: {push_result.stderr[:300]}",
                    duration_seconds=time.time() - start,
                    model_used=model,
                )

            self.log(
                "aider.review_complete",
                f"Review iteration done: {len(files_changed)} files on {branch}",
                task_id=task_id,
            )

            return AiderResult(
                success=True,
                files_changed=files_changed,
                commit_hashes=commit_hashes,
                branch=branch,
                aider_output=aider_output,
                duration_seconds=time.time() - start,
                model_used=model,
            )

        except subprocess.TimeoutExpired:
            return AiderResult(
                success=False,
                branch=branch,
                error=f"Aider review iteration timed out after {AIDER_TIMEOUT_SECONDS}s",
                duration_seconds=time.time() - start,
                model_used=model,
            )
        except Exception as e:
            return AiderResult(
                success=False,
                branch=branch,
                error=f"{type(e).__name__}: {e}",
                duration_seconds=time.time() - start,
                model_used=model,
            )


def is_aider_available() -> bool:
    """Check if Aider CLI is installed and accessible."""
    try:
        result = subprocess.run(
            ["aider", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
