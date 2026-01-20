import os
import subprocess
from pathlib import Path
from typing import List

import pytest

import hive


@pytest.fixture
def repo_config() -> hive.RepoConfig:
    return hive.RepoConfig(owner="owner", name="repo", default_branch="main")


# RepoConfig tests


def test_repo_config_full_name(repo_config: hive.RepoConfig) -> None:
    assert repo_config.full_name == "owner/repo"


# run_command tests


def test_run_command_returns_stdout_on_success(monkeypatch) -> None:
    captured_args = {}

    def fake_run(args: List[str], cwd=None, check=None, capture_output=None, text=None):
        captured_args["args"] = args
        captured_args["cwd"] = cwd
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="output\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = hive.run_command(["echo", "hi"], cwd=Path("/tmp"))

    assert result == "output\n"
    assert captured_args["args"] == ["echo", "hi"]
    assert captured_args["cwd"] == str(Path("/tmp"))


def test_run_command_raises_called_process_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["cmd"],
            stdout="stdout",
            stderr="stderr",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        hive.run_command(["cmd"])


def test_run_command_raises_os_error(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise OSError("exec format error")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(OSError):
        hive.run_command(["cmd"])


# get_github_token tests


def test_get_github_token_returns_value(monkeypatch) -> None:
    token = "test-token"
    monkeypatch.setenv(hive.GITHUB_TOKEN_ENV_VAR, token)

    assert hive.get_github_token() == token


def test_get_github_token_raises_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv(hive.GITHUB_TOKEN_ENV_VAR, raising