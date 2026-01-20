import logging
from typing import Final

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)
GREETING_MESSAGE: Final[str] = "Hello World"


def get_greeting() -> str:
    """Return a greeting message.

    Returns:
        str: The greeting message "Hello World".
    """
    LOGGER.debug("Generating greeting message.")
    return GREETING_MESSAGE


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    LOGGER.info(get_greeting())