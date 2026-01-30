import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

LOGGER_NAME: str = "comment_module"
DEFAULT_README_PATH: Path = Path("README.md")
COMMENT_TEMPLATE: str = "\n<!-- Automated comment: {timestamp} -->\n"
TIMESTAMP_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"


logger = logging.getLogger(LOGGER_NAME)


def get_current_timestamp() -> str:
    """Get the current UTC timestamp formatted for logging and comments.

    Returns:
        str: Current UTC timestamp in ISO-like format.
    """
    now_utc: datetime = datetime.now(timezone.utc)
    return now_utc.strftime(TIMESTAMP_FORMAT)


def add_comment_to_readme(readme_path: Path) -> None:
    """Append a timestamped comment to the bottom of the README file.

    Args:
        readme_path (Path): Path to the README markdown file.

    Raises:
        FileNotFoundError: If the README file does not exist.
        PermissionError: If the process lacks permissions to modify the file.
        OSError: For other I/O-related errors.
    """
    logger.debug("Preparing to append comment to README at path: %s", readme_path)

    if not readme_path.exists():
        logger.error("README file does not exist at path: %s", readme_path)
        raise FileNotFoundError(f"README file not found: {readme_path}")

    if not readme_path.is_file():
        logger.error("Path is not a file: %s", readme_path)
        raise OSError(f"Path is not a file: {readme_path}")

    timestamp: str = get_current_timestamp()
    comment: str = COMMENT_TEMPLATE.format(timestamp=timestamp)

    logger.debug("Generated comment to append: %s", comment.strip())

    try:
        with readme_path.open(mode="a", encoding="utf-8") as readme_file:
            readme_file.write(comment)
        logger.info("Successfully appended comment to README at %s", readme_path)
    except PermissionError as exc:
        logger.exception("Permission denied when writing to README at %s", readme_path)
        raise
    except OSError as exc:
        logger.exception("OS error when writing to README at %s: %s", readme_path, exc)
        raise


def parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args (Optional[list[str]]): List of arguments, excluding the program name.
            If None, argparse will use sys.argv.

    Returns:
        argparse.Namespace: Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Append a timestamped HTML comment to the bottom of a README.md file "
            "to verify execution of the code pipeline."
        )
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=DEFAULT_README_PATH,
        help=(
            "Path to the README file to modify. "
            f"Defaults to '{DEFAULT_README_PATH}'."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging verbosity level (default: INFO).",
    )
    return parser.parse_args(args=args)


def configure_logging(level: str) -> None:
    """Configure the root logger for the module.

    Args:
        level (str): Logging level name (e.g., 'INFO', 'DEBUG').
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.debug("Logging configured with level: %s", level)


def main() -> None:
    """Command-line entry point for appending a timestamp comment to README."""
    parsed_args = parse_args()
    configure_logging(parsed_args.log_level)

    logger.debug(
        "Starting README comment appender with arguments: %s", parsed_args
    )

    try:
        add_comment_to_readme(parsed_args.readme)
    except FileNotFoundError:
        logger.error("Aborting: README file not found.")
        raise SystemExit(1)
    except PermissionError:
        logger.error("Aborting: Permission denied when writing to README.")
        raise SystemExit(1)
    except OSError:
        logger.error("Aborting: An OS error occurred while updating README.")
        raise SystemExit(1)

    logger.debug("README comment appender completed successfully.")


if __name__ == "__main__":
    main()