import os
import logging
from pathlib import Path
from typing import List, Union
from dotenv import load_dotenv

logger = logging.getLogger("onboarding_buddy.config")

# Load .env file from root directory ONLY for local development.
# In production, environment variables must be injected via runtime environment / deployment secrets.
env_path = Path(__file__).parent / ".env"
if env_path.is_file():
    load_dotenv(dotenv_path=env_path, override=False)
else:
    logger.info(".env file not present. Relying strictly on process environment variables.")


def _parse_bool(val: Union[str, bool, None], default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes", "t", "on")


def _parse_origins(origins_val: Union[str, List[str], None]) -> List[str]:
    if not origins_val:
        return []
    if isinstance(origins_val, list):
        return [str(o).strip() for o in origins_val if str(o).strip()]
    return [o.strip() for o in str(origins_val).split(",") if o.strip()]


class Settings:
    """Enterprise application configuration supporting local development and secure production deployments."""

    def __init__(self, **kwargs):
        # Environment mode: 'development', 'production', or 'testing'
        if "ENVIRONMENT" in kwargs and kwargs["ENVIRONMENT"] is not None:
            self.ENVIRONMENT: str = str(kwargs["ENVIRONMENT"]).strip().lower()
        else:
            self.ENVIRONMENT = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).strip().lower()

        # Debug mode - explicitly disabled by default in production
        if "DEBUG" in kwargs and kwargs["DEBUG"] is not None:
            self.DEBUG: bool = _parse_bool(kwargs["DEBUG"])
        else:
            _debug_raw = os.getenv("DEBUG")
            if _debug_raw is not None:
                self.DEBUG: bool = _parse_bool(_debug_raw)
            else:
                self.DEBUG: bool = False if self.ENVIRONMENT == "production" else True

        # Server network binding
        _default_host = "0.0.0.0" if self.ENVIRONMENT == "production" else "127.0.0.1"
        if "HOST" in kwargs and kwargs["HOST"] is not None:
            self.HOST: str = str(kwargs["HOST"]).strip()
        else:
            self.HOST = os.getenv("HOST", _default_host).strip()

        if "PORT" in kwargs and kwargs["PORT"] is not None:
            self.PORT: int = int(kwargs["PORT"])
        else:
            self.PORT = int(os.getenv("PORT", "8000"))

        # Groq AI Service Secret (MUST be provided as a deployment secret in production)
        if "GROQ_API_KEY" in kwargs and kwargs["GROQ_API_KEY"] is not None:
            self.GROQ_API_KEY: str = str(kwargs["GROQ_API_KEY"]).strip()
        else:
            self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

        if "GROQ_MODEL" in kwargs and kwargs["GROQ_MODEL"] is not None:
            self.GROQ_MODEL: str = str(kwargs["GROQ_MODEL"]).strip()
        else:
            self.GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

        # CORS Configuration
        if "CORS_ALLOWED_ORIGINS" in kwargs and kwargs["CORS_ALLOWED_ORIGINS"] is not None:
            self.CORS_ALLOWED_ORIGINS: List[str] = _parse_origins(kwargs["CORS_ALLOWED_ORIGINS"])
        else:
            _raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", os.getenv("ALLOWED_ORIGINS", ""))
            self.CORS_ALLOWED_ORIGINS = _parse_origins(_raw_origins)

        # API Documentation toggle
        if "ENABLE_DOCS" in kwargs and kwargs["ENABLE_DOCS"] is not None:
            self.ENABLE_DOCS: bool = _parse_bool(kwargs["ENABLE_DOCS"])
        else:
            _docs_raw = os.getenv("ENABLE_DOCS")
            if _docs_raw is not None:
                self.ENABLE_DOCS: bool = _parse_bool(_docs_raw)
            else:
                self.ENABLE_DOCS: bool = (self.ENVIRONMENT != "production")

        # Logging level
        _default_log = "INFO" if self.ENVIRONMENT == "production" else "DEBUG"
        if "LOG_LEVEL" in kwargs and kwargs["LOG_LEVEL"] is not None:
            self.LOG_LEVEL: str = str(kwargs["LOG_LEVEL"]).strip().upper()
        else:
            self.LOG_LEVEL = os.getenv("LOG_LEVEL", _default_log).strip().upper()

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT == "testing"

    @property
    def is_groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here")

    @property
    def masked_groq_key(self) -> str:
        """Returns a safe masked representation of the Groq API key (never leaks the full secret)."""
        if not self.GROQ_API_KEY or self.GROQ_API_KEY == "your_groq_api_key_here":
            return "not-configured"
        if len(self.GROQ_API_KEY) <= 8:
            return "configured (masked)"
        return f"{self.GROQ_API_KEY[:4]}...{self.GROQ_API_KEY[-4:]}"

    def get_cors_origins(self) -> List[str]:
        """Returns the list of allowed CORS origins based on environment."""
        if self.CORS_ALLOWED_ORIGINS:
            return _parse_origins(self.CORS_ALLOWED_ORIGINS)
        if self.is_production:
            # Production: strict by default, never return wildcard "*"
            return []
        # Development defaults:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ]


settings = Settings()
