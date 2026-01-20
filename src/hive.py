import datetime
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


GITHUB_API_URL: str = "https://api.github.com"
REPO_OWNER: str = "SpartanPlumbingJosh"
REPO_NAME: str = "spartan-hq"
DEFAULT_BRANCH: str = "master"
TARGET_FILE_REL_PATH: str = "app/hive-command/tasks/page.tsx"
GITHUB_TOKEN_ENV_VAR: str = "GITHUB_TOKEN"
REQUEST_TIMEOUT_SECONDS: int = 15
MERGE_METHOD: str = "squash"

OLD_ENDPOINT_SUBSTRING: str = "/api/tasks"
NEW_ENDPOINT_SUBSTRING: str = "/api/hive-command/tasks"

BRANCH_NAME_PREFIX: str = "fix-hive-command-tasks-endpoint"
COMMIT_MESSAGE: str = "Fix Hive Command tasks API endpoint path"
PR_TITLE: str = "Fix Hive Command tasks API endpoint path"
PR_BODY: str = (
    "This PR updates the Hive Command Tasks page so that it calls the correct API "
    "endpoint:\n\n"
    "- Changes `/api/tasks` to `/api/hive-command/tasks` in "
    "`app/hive-command/tasks/page.tsx`.\n"
    "- Ensures the Tasks page no longer returns a 404 when loading tasks.\n\n"
    "Acceptance criteria:\n"
    "1. Tasks page loads without 404 error\n"
    "2. API call goes to `/api/hive-command/tasks`\n"
    "3. Tasks are displayed correctly in the UI\n"
    "4. PR created and merged\n"
)


@dataclass
class RepoConfig:
    """Configuration for the target GitHub repository.

    Attributes:
        owner: Owner of the repository.
        name: Name of the repository.
        default_branch: Default branch name (e.g., 'master' or 'main').
    """

    owner: str
    name: str
    default_branch: str = DEFAULT_BRANCH

    @property
    def full_name(self) -> str:
        """Return the full repository name in 'owner/name' format.

        Returns:
            Full repository name.
        """
        return f"{self.owner}/{self.name}"


def run_command(args: list[str], cwd: Optional[Path] = None) -> str:
    """Run a shell command and return its standard output.

    Args:
        args: Command and arguments to execute.
        cwd: Optional working directory.

    Returns:
        Standard output from the command.

    Raises:
        subprocess.CalledProcessError: If the command exits with a non-zero status.
        OSError: If the command cannot be executed.
    """
    logging.debug("Running command: %s (cwd=%s)", " ".join(args), str(cwd) if cwd else None)
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        logging.error(
            "Command failed: %s\nReturn code: %s\nSTDOUT: %s\nSTDERR: %s",
            " ".join(args),
            exc.returncode,
            exc.stdout,
            exc.stderr,
        )
        raise
    except OSError as exc:
        logging.error("OS error while running command '%s': %s", " ".join(args), exc)
        raise

    logging.debug("Command output: %s", completed.stdout.strip())
    return completed.stdout


def get_github_token() -> str:
    """Retrieve the GitHub token from environment variables.

    Returns:
        GitHub personal access token string.

    Raises:
        KeyError: If the token environment variable is not set.
    """
    try:
        token = os.environ[GITHUB_TOKEN_ENV_VAR]
    except KeyError as exc:
        logging.error(
            "GitHub token environment variable '%s' is not set.",
            GITHUB_TOKEN_ENV_VAR,
        )
        raise
    if not token:
        logging.error(
            "GitHub token environment variable '%s' is empty.",
            GITHUB_TOKEN_ENV_VAR,
        )
        raise KeyError(f"Environment variable {GITHUB_TOKEN_ENV_VAR} is empty")
    logging.debug("GitHub token retrieved from environment.")
    return token


def build_clone_url(config: RepoConfig) -> str:
    """Build the HTTPS clone URL for the repository.

    Args:
        config: Repository configuration.

    Returns:
        HTTPS clone URL.
    """
    url = f"https://github.com/{config.full_name}.git"
    logging.debug("Constructed clone URL: %s", url)
    return url


def build_authenticated_push_url(config: RepoConfig, token: str) -> str:
    """Build an authenticated HTTPS remote URL with an access token.

    Args:
        config: Repository configuration.
        token: GitHub personal access token.

    Returns:
        Authenticated HTTPS remote URL suitable for git push.
    """
    # Using x-access-token is the recommended pattern for GitHub.
    url = f"https://x-access-token:{token}@github.com/{config.full_name}.git"
    logging.debug("Constructed authenticated remote URL (token redacted).")
    return url


def clone_repository(config: RepoConfig, base_dir: Path) -> Path:
    """Clone the target repository into the base directory.

    Args:
        config: Repository configuration.
        base_dir: Directory into which the repository will be cloned.

    Returns:
        Path to the cloned repository.

    Raises:
        subprocess.CalledProcessError: If git clone fails.
        OSError: If git cannot be executed.
    """
    clone_url = build_clone_url(config)
    repo_dir = base_dir / config.name
    logging.info(
        "Cloning repository %s (branch=%s) into %s",
        config.full_name,
        config.default_branch,
        repo_dir,
    )
    run_command(
        [
            "git",
            "clone",
            "--branch",
            config.default_branch,
            "--single-branch",
            clone_url,
            str(repo_dir),
        ]
    )
    return repo_dir


def create_feature_branch(repo_dir: Path, branch_name: str) -> None:
    """Create and check out a new feature branch.

    Args:
        repo_dir: Path to the repository.
        branch_name: Name of the new branch.

    Raises:
        subprocess.CalledProcessError: If git commands fail.
    """
    logging.info("Creating and checking out new branch: %s", branch_name)
    run_command(["git", "checkout", config.default_branch], cwd=repo_dir)  # type: ignore[name-defined]
    run_command(["git", "checkout", "-b", branch_name], cwd=repo_dir)


def update_remote_with_token(repo_dir: Path, config: RepoConfig, token: str) -> None:
    """Update the 'origin' remote URL to use token-based authentication.

    Args:
        repo_dir: Path to the repository.
        config: Repository configuration.
        token: GitHub personal access token.

    Raises:
        subprocess.CalledProcessError: If git remote command fails.
    """
    authenticated_url = build_authenticated_push_url(config, token)
    logging.info("Updating 'origin' remote to use authenticated URL (token redacted).")
    run_command(["git", "remote", "set-url", "origin", authenticated_url], cwd=repo_dir)


def read_file_text(file_path: Path) -> str:
    """Read and return the text content of a file.

    Args:
        file_path: Path to the file.

    Returns:
        File contents as a string.

    Raises:
        OSError: If the file cannot be read.
    """
    logging.debug("Reading file: %s", file_path)
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as exc:
        logging.error("Failed to read file %s: %s", file_path, exc)
        raise


def write_file_text(file_path: Path, content: str) -> None:
    """Write text content to a file.

    Args:
        file_path: Path to the file.
        content: Text content to write.

    Raises:
        OSError: If the file cannot be written.
    """
    logging.debug("Writing updated content to file: %s", file_path)
    try:
        file_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logging.error("Failed to write file %s: %s", file_path, exc)
        raise


def update_tasks_page_file(repo_dir: Path) -> bool:
    """Update the Hive Command tasks page to use the correct API endpoint.

    This function searches for the old `/api/tasks` endpoint and replaces the first
    occurrence with `/api/hive-command/tasks`.

    Args:
        repo_dir: Path to the cloned repository.

    Returns:
        True if the file was modified, False if no changes were necessary.

    Raises:
        FileNotFoundError: If the target file does not exist.
        ValueError: If the file does not contain the expected endpoint substring.
        OSError: If there is an I/O error reading or writing the file.
    """
    target_path = repo_dir / TARGET_FILE_REL_PATH
    if not target_path.is_file():
        logging.error("Target file not found: %s", target_path)
        raise FileNotFoundError(f"Target file not found: {target_path}")

    original_content = read_file_text(target_path)
    if NEW_ENDPOINT_SUBSTRING in original_content:
        logging.info(
            "File %s already uses the new endpoint '%s'. No changes needed.",
            target_path,
            NEW_ENDPOINT_SUBSTRING,
        )
        return False

    if OLD_ENDPOINT_SUBSTRING not in original_content:
        logging.error(
            "Expected old endpoint substring '%s' not found in %s",
            OLD_ENDPOINT_SUBSTRING,
            target_path,
        )
        raise ValueError(
            f"Expected old endpoint substring '{OLD_ENDPOINT_SUBSTRING}' not found in {target_path}"
        )

    updated_content = original_content.replace(
        OLD_ENDPOINT_SUBSTRING, NEW_ENDPOINT_SUBSTRING, 1
    )

    if updated_content == original_content:
        logging.info("No changes made to file %s.", target_path)
        return False

    write_file_text(target_path, updated_content)
    logging.info(
        "Updated endpoint in %s from '%s' to '%s'.",
        target_path,
        OLD_ENDPOINT_SUBSTRING,
        NEW_ENDPOINT_SUBSTRING,
    )
    return True


def stage_and_commit_changes(repo_dir: Path, message: str) -> None:
    """Stage changes and create a git commit.

    Args:
        repo_dir: Path to the repository.
        message: Commit message.

    Raises:
        subprocess.CalledProcessError: If git add or git commit fails.
    """
    logging.info("Staging changes for commit.")
    run_command(["git", "add", TARGET_FILE_REL_PATH], cwd=repo_dir)

    status_output = run_command(["git", "status", "--porcelain"], cwd=repo_dir)
    if not status_output.strip():
        logging.info("No changes to commit.")
        return

    logging.info("Creating commit with message: %s", message)
    run_command(["git", "commit", "-m", message], cwd=repo_dir)


def push_branch(repo_dir: Path, branch_name: str) -> None:
    """Push the branch to the origin remote.

    Args:
        repo_dir: Path to the