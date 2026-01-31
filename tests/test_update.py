import importlib
import logging
import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


def _import_update_module():
    for name in ("juggernaut.update", "update"):
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            continue
    raise RuntimeError("Could not import update module as 'juggernaut.update' or 'update'")


update = _import_update_module()


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


def test_updatepaths_is_frozen_dataclass(repo_root: Path):
    paths = update.UpdatePaths(repo_root=repo_root, chat_page=repo_root / "a", message_bubble=repo_root / "b")
    with pytest.raises(FrozenInstanceError):
        paths.repo_root = repo_root / "other"


def test_configure_logging_uses_uppercase_level_and_calls_basicconfig(monkeypatch):
    captured = {}

    def fake_basicConfig(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(update.logging, "basicConfig", fake_basicConfig)

    update.configure_logging("debug")

    assert captured["level"] == logging.DEBUG
    assert "%(asctime)s" in captured["format"]
    assert "%(levelname)s" in captured["format"]
    assert "%(name)s" in captured["format"]
    assert "%(message)s" in captured["format"]


def test_configure_logging_unknown_level_falls_back_to_info(monkeypatch):
    captured = {}

    def fake_basicConfig(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(update.logging, "basicConfig", fake_basicConfig)

    update.configure_logging("not-a-level")

    assert captured["level"] == logging.INFO


def test_resolve_paths_builds_expected_paths(repo_root: Path):
    paths = update.resolve_paths(repo_root)

    assert isinstance(paths, update.UpdatePaths)
    assert paths.repo_root == repo_root
    assert paths.chat_page == repo_root / "spartan-hq" / "app" / "(app)" / "chat" / "page.tsx"
    assert paths.message_bubble == repo_root / "spartan-hq" / "components" / "chat" / "MessageBubble.tsx"


def test_ensure_parent_dir_creates_missing_parents(tmp_path: Path):
    target = tmp_path / "a" / "b" / "file.txt"
    assert not target.parent.exists()

    update.ensure_parent_dir(target)

    assert target.parent.exists()
    assert target.parent.is_dir()


def test_ensure_parent_dir_noop_when_parent_exists(tmp_path: Path):
    parent = tmp_path / "exists"
    parent.mkdir()
    target = parent / "file.txt"

    update.ensure_parent_dir(target)

    assert parent.exists()
    assert parent.is_dir()


def test_read_text_if_exists_returns_none_when_missing(tmp_path: Path):
    missing = tmp_path / "missing.txt"
    assert update.read_text_if_exists(missing) is None


def test_read_text_if_exists_reads_existing_file_with_expected_content(tmp_path: Path):
    p = tmp_path / "hello.txt"
    p.write_text("hello", encoding=update.ENCODING)

    assert update.read_text_if_exists(p) == "hello"


def test_read_text_if_exists_raises_oserror_when_read_fails(tmp_path: Path, monkeypatch):
    p = tmp_path / "boom.txt"
    p.write_text("x", encoding=update.ENCODING)

    def fake_read_text(*args, **kwargs):
        raise OSError("cannot read")

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    with pytest.raises(OSError, match="cannot read"):
        update.read_text_if_exists(p)


def test_backup_file_noop_when_source_missing(tmp_path: Path):
    p = tmp_path / "nope.txt"
    update.backup_file(p)
    assert not (tmp_path / ("nope.txt" + update.BACKUP_SUFFIX)).exists()


def test_backup_file_creates_bak_copy_when_file_exists(tmp_path: Path):
    p = tmp_path / "data.txt"
    p.write_text("content", encoding=update.ENCODING)

    update.backup_file(p)

    backup = tmp_path / ("data.txt" + update.BACKUP_SUFFIX)
    assert backup.exists()
    assert backup.read_text(encoding=update.ENCODING) == "content"


def test_backup_file_propagates_copy_errors(tmp_path: Path, monkeypatch):
    p = tmp_path / "data.txt"
    p.write_text("content", encoding=update.ENCODING)

    def fake_copy2(src, dst, *args, **kwargs):
        raise OSError("copy failed")

    monkeypatch.setattr(update.shutil, "copy2", fake_copy2)

    with pytest.raises(OSError, match="copy failed"):
        update.backup_file(p)


def test_write_text_atomic_creates_parent_writes_content_and_removes_tmp(tmp_path: Path):
    target = tmp_path / "nested" / "dir" / "file.txt"
    assert not target.parent.exists()

    update.write_text_atomic(target, "abc")

    assert target.exists()
    assert target.read_text(encoding=update.ENCODING) == "abc"
    tmp_path_expected = target.with_suffix(target.suffix + ".tmp")
    assert not tmp_path_expected.exists()


def test_write_text_atomic_works_for_paths_without_suffix(tmp_path: Path):
    target = tmp_path / "nested" / "file"  # no suffix
    update.write_text_atomic(target, "payload")

    assert target.exists()
    assert target.read_text(encoding=update.ENCODING) == "payload"
    tmp_path_expected = target.with_suffix(target.suffix + ".tmp")
    assert not tmp_path_expected.exists()
    assert tmp_path_expected.suffix == ".tmp"


def test_write_text_atomic_overwrites_existing_file(tmp_path: Path):
    target = tmp_path / "file.txt"
    target.write_text("old", encoding=update.ENCODING)

    update.write_text_atomic(target, "new")

    assert target.read_text(encoding=update.ENCODING) == "new"


def test_write_text_atomic_propagates_replace_errors_and_leaves_tmp(tmp_path: Path, monkeypatch):
    target = tmp_path / "file.txt"

    def fake_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(update.os, "replace", fake_replace)

    with pytest.raises(OSError, match="replace failed"):
        update.write_text_atomic(target, "data")

    tmp_path_expected = target.with_suffix(target.suffix + ".tmp")
    assert tmp_path_expected.exists()
    assert tmp_path_expected.read_text(encoding=update.ENCODING) == "data"
    assert not target.exists()


def test_generate_message_bubble_tsx_returns_nonempty_string_with_expected_markers():
    content = update.generate_message_bubble_tsx()
    assert isinstance(content, str)
    assert content.strip() != ""
    assert "'use client';" in content
    assert "export type ChatMessage" in content
    assert "const MAX_PREVIEW_CHARS = 240;" in content
    assert "function safeJsonParse" in content
    assert "function StructuredDataRenderer" in content