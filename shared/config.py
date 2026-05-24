"""
config.py — Centralized configuration for the PoC Platform.

Loads environment variables from a .env file on import and exposes them
as class-level attributes on the `Config` class. A module-level singleton
`config` is provided for convenience.

Usage:
    from shared.config import config
    api_key = config.ANTHROPIC_API_KEY
"""

import os
from dotenv import load_dotenv

# Load .env file from repo root (two levels up from this file's location)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=_env_path, override=False)


class Config:
    """
    Application configuration sourced from environment variables.

    All attributes are read from the process environment (populated by
    python-dotenv from a .env file). Sensitive values are never stored
    in source control — only their names are declared here.
    """

    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # --- Streamlit Auth ---
    STREAMLIT_USERNAME: str = os.getenv("STREAMLIT_USERNAME", "")
    STREAMLIT_PASSWORD: str = os.getenv("STREAMLIT_PASSWORD", "")

    # --- Runtime ---
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # --- Email / SMTP ---
    EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    @classmethod
    def validate(cls) -> None:
        """
        Validate that required configuration values are present.

        Raises:
            ValueError: If ANTHROPIC_API_KEY, STREAMLIT_USERNAME, or
                        STREAMLIT_PASSWORD are missing.
        """
        missing = []
        for attr in ("ANTHROPIC_API_KEY", "STREAMLIT_USERNAME", "STREAMLIT_PASSWORD"):
            if not getattr(cls, attr):
                missing.append(attr)
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please set them in your .env file or environment."
            )

    @property
    def is_prod(self) -> bool:
        """Return True when running in the production environment."""
        return self.ENVIRONMENT.lower() == "production"


# Module-level singleton — import this in other modules
config = Config()
