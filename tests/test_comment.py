import argparse
import logging
from datetime import datetime
from pathlib import Path

import pytest

import comment


class FixedDateTime(datetime):
    """Fixed datetime class for deterministic timestamp testing."""

    @classmethod
    def now(cls, tz=None):
        # 2023-01-02T03:04:05Z
        return cls(2023, 1, 2, 3, 4, 5, tzinfo=tz)


@pytest.fixture
def readme_file(tmp_path: Path) -> Path:
    """Create a temporary README file."""
    readme = tmp_path / "README.md"
    readme.write_text("Initial content\n", encoding="utf-8")
    return readme


def test_get_current_timestamp_fixed(monkeypatch):
    """get_current_timestamp should use UTC and the configured format."""
    # Patch the datetime class used by the module
    monkeypatch.setattr(comment, "datetime", FixedDateTime)

    timestamp = comment.get_current_timestamp()
    assert timestamp == "2023-01-02T03:04:05Z"


def test_get_current_timestamp_matches_format():
    """get_current_timestamp should return a value that matches TIMESTAMP_FORMAT."""
    timestamp = comment.get_current_timestamp()
    # Should be parseable with the given format; this will raise if invalid.
    parsed = datetime.strptime(timestamp, comment.TIMESTAMP_FORMAT)
    # Ensure the 'Z' (UTC marker) is present as literal
    assert timestamp.endswith("Z")
    assert isinstance(parsed, datetime)


def test_add_comment_to_readme_appends_comment_with_timestamp(
    readme_file: Path, monkeypatch, caplog
):
    """add_comment_to_readme should append a formatted comment with a fixed timestamp."""
    fixed_ts = "2020-01-01T00:00:00Z"
    monkeypatch.setattr(comment, "get_current_timestamp", lambda: fixed_ts)

    with caplog.at_level(logging.DEBUG, logger=comment.LOGGER_NAME):
        comment.add_comment_to_readme(readme_file)

    contents = readme_file.read_text(encoding="utf-8")
    expected_comment = comment.COMMENT_TEMPLATE.format(timestamp=fixed_ts)
    assert contents.endswith(expected_comment)

    # Verify some logging occurred
    assert any(
        "Preparing to append comment to README" in record.message
        for record in caplog.records
    )
    assert any(
        "Successfully appended comment to README" in record.message
        for record in caplog.records
    )


def test_add_comment_to_readme_raises_file_not_found(tmp_path: Path, caplog):
    """add_comment_to_readme should raise FileNotFoundError when file does not exist."""
    missing_readme = tmp_path / "MISSING_README.md"

    with caplog.at_level(logging.ERROR, logger=comment.LOGGER_NAME):
        with pytest.raises(FileNotFoundError) as excinfo:
            comment.add_comment_to_readme(missing_readme)

    assert "README file not found" in str(excinfo.value)
    assert any(
        "README file does not exist at path" in record.message
        for record in caplog.records
    )


def test_add_comment_to_readme_raises_oserror_when_path_is_directory(
    tmp_path: Path, caplog
):
    """add_comment_to_readme should raise OSError when given a directory instead of a file."""
    directory_path = tmp_path / "some_dir"
    directory_path.mkdir()

    with caplog.at_level(logging.ERROR, logger=comment.LOGGER_NAME):
        with pytest.raises(OSError) as excinfo:
            comment.add_comment_to_readme(directory_path)

    assert "Path