"""
test_hello.py: Demonstrates basic Python code structure and best practices.
"""

import logging

# Constants
LOG_LEVEL = logging.INFO

class HelloWorld:
    """A simple class that prints a greeting message."""

    def __init__(self, name: str) -> None:
        """Initialize the HelloWorld object with a name."""
        self.name = name

    def greet(self) -> None:
        """Print a greeting message using the stored name."""
        logging.info(f"Hello, {self.name}!")

def main() -> None:
    """Run the main program."""
    logging.basicConfig(level=LOG_LEVEL)
    hello_world = HelloWorld("Alice")
    hello_world.greet()

if __name__ == "__main__":
    main()