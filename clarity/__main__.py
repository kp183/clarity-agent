"""Allow running Clarity via `python -m clarity`."""
from .cli.app import app

if __name__ == "__main__":
    app()
