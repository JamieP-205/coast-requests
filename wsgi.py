"""The entry point PythonAnywhere runs. It loads the settings from .env next
to this file, then creates the app. See docs/deploying.md."""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from coast_requests import create_app  # noqa: E402  (settings must load first)

application = create_app()
