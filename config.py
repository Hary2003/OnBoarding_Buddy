import os
import logging
from pathlib import Path
from typing import List, Union
from urllib.parse import urlsplit, urlunsplit
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


def _mask_url(url: str) -> str:
    """Masks credentials in a database URL so secrets are never printed to logs or APIs."""
    if not url:
        return "not-configured"
    try:
        parsed = urlsplit(url)
        if parsed.password:
            user = parsed.username or "user"
            host = parsed.hostname or "localhost"
            port_str = f":{parsed.port}" if parsed.port else ""
            netloc = f"{user}:****@{host}{port_str}"
            return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))
        return url
    except Exception:
        return "configured (masked)"


def _is_container() -> bool:
    """Detect whether running inside a Docker or OCI container."""
    if os.getenv("DOCKER_CONTAINER", "").strip().lower() in ("true", "1", "yes"):
        return True
    if os.getenv("RUNNING_IN_DOCKER", "").strip().lower() in ("true", "1", "yes"):
        return True
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup_path = Path("/proc/1/cgroup")
        if cgroup_path.exists():
            content = cgroup_path.read_text(encoding="utf-8", errors="ignore")
            if any(term in content for term in ("docker", "kubepods", "containerd")):
                return True
    except Exception:
        pass
    return False


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

        # Container execution detection
        if "IS_CONTAINER" in kwargs and kwargs["IS_CONTAINER"] is not None:
            self.IS_CONTAINER: bool = _parse_bool(kwargs["IS_CONTAINER"])
        else:
            _container_raw = os.getenv("DOCKER_CONTAINER", os.getenv("RUNNING_IN_DOCKER"))
            if _container_raw is not None:
                self.IS_CONTAINER = _parse_bool(_container_raw)
            else:
                self.IS_CONTAINER = _is_container()

        # Server network binding
        # In container environments, binding to 127.0.0.1 or localhost isolates the server from host port mapping.
        _default_host = "0.0.0.0" if (self.ENVIRONMENT == "production" or self.IS_CONTAINER) else "127.0.0.1"
        if "HOST" in kwargs and kwargs["HOST"] is not None:
            raw_host = str(kwargs["HOST"]).strip()
        else:
            raw_host = os.getenv("HOST", _default_host).strip()

        if self.IS_CONTAINER and raw_host in ("127.0.0.1", "localhost"):
            self.HOST: str = "0.0.0.0"
        else:
            self.HOST: str = raw_host

        if "PORT" in kwargs and kwargs["PORT"] is not None:
            self.PORT: int = int(kwargs["PORT"])
        else:
            self.PORT = int(os.getenv("PORT", "8000"))

        # Auto-reload configuration
        # Auto-reload is disabled in production and Docker containers to eliminate file-watching overhead and ensure container stability.
        if "RELOAD" in kwargs and kwargs["RELOAD"] is not None:
            self.RELOAD: bool = _parse_bool(kwargs["RELOAD"])
        else:
            _reload_raw = os.getenv("RELOAD", os.getenv("UVICORN_RELOAD"))
            if _reload_raw is not None:
                self.RELOAD = _parse_bool(_reload_raw)
            elif self.IS_CONTAINER or self.ENVIRONMENT == "production":
                self.RELOAD = False
            else:
                self.RELOAD = self.DEBUG

        # Groq AI Service Secret (MUST be provided as a deployment secret in production)
        if "GROQ_API_KEY" in kwargs and kwargs["GROQ_API_KEY"] is not None:
            self.GROQ_API_KEY: str = str(kwargs["GROQ_API_KEY"]).strip()
        else:
            self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

        if "GROQ_MODEL" in kwargs and kwargs["GROQ_MODEL"] is not None:
            self.GROQ_MODEL: str = str(kwargs["GROQ_MODEL"]).strip()
        else:
            self.GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

        # PostgreSQL Database Configuration (Neon PostgreSQL)
        if "DATABASE_URL" in kwargs and kwargs["DATABASE_URL"] is not None:
            self.DATABASE_URL: str = str(kwargs["DATABASE_URL"]).strip()
        else:
            self.DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

        # Connection Pool Settings
        self.DB_POOL_SIZE: int = int(kwargs.get("DB_POOL_SIZE") or os.getenv("DB_POOL_SIZE", "10"))
        self.DB_MAX_OVERFLOW: int = int(kwargs.get("DB_MAX_OVERFLOW") or os.getenv("DB_MAX_OVERFLOW", "20"))
        self.DB_POOL_TIMEOUT: int = int(kwargs.get("DB_POOL_TIMEOUT") or os.getenv("DB_POOL_TIMEOUT", "30"))
        self.DB_POOL_RECYCLE: int = int(kwargs.get("DB_POOL_RECYCLE") or os.getenv("DB_POOL_RECYCLE", "300"))

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

        # Rate Limiting Configuration (per client IP sliding-window limit)
        if "RATE_LIMIT_ENABLED" in kwargs and kwargs["RATE_LIMIT_ENABLED"] is not None:
            self.RATE_LIMIT_ENABLED: bool = _parse_bool(kwargs["RATE_LIMIT_ENABLED"])
        else:
            self.RATE_LIMIT_ENABLED = _parse_bool(os.getenv("RATE_LIMIT_ENABLED", "true"), default=True)

        if "RATE_LIMIT_PER_MINUTE" in kwargs and kwargs["RATE_LIMIT_PER_MINUTE"] is not None:
            self.RATE_LIMIT_PER_MINUTE: int = int(kwargs["RATE_LIMIT_PER_MINUTE"])
        else:
            self.RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

        # API Authentication Configuration (optional API Key / Bearer token gate)
        if "API_AUTH_ENABLED" in kwargs and kwargs["API_AUTH_ENABLED"] is not None:
            self.API_AUTH_ENABLED: bool = _parse_bool(kwargs["API_AUTH_ENABLED"])
        else:
            self.API_AUTH_ENABLED = _parse_bool(os.getenv("API_AUTH_ENABLED", "false"), default=False)

        if "API_KEY" in kwargs and kwargs["API_KEY"] is not None:
            self.API_KEY: str = str(kwargs["API_KEY"]).strip()
        else:
            self.API_KEY = os.getenv("API_KEY", os.getenv("ONBOARDING_API_KEY", "")).strip()

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
    def is_container(self) -> bool:
        return self.IS_CONTAINER

    @property
    def is_groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here")

    @property
    def is_db_configured(self) -> bool:
        return bool(self.DATABASE_URL and "user:password" not in self.DATABASE_URL)

    @property
    def masked_groq_key(self) -> str:
        """Returns a safe masked representation of the Groq API key (never leaks the full secret)."""
        if not self.GROQ_API_KEY or self.GROQ_API_KEY == "your_groq_api_key_here":
            return "not-configured"
        if len(self.GROQ_API_KEY) <= 8:
            return "configured (masked)"
        return f"{self.GROQ_API_KEY[:4]}...{self.GROQ_API_KEY[-4:]}"

    @property
    def masked_database_url(self) -> str:
        """Returns a sanitized representation of the database URL with password stripped."""
        return _mask_url(self.DATABASE_URL)

    @property
    def is_auth_configured(self) -> bool:
        return bool(self.API_AUTH_ENABLED and self.API_KEY)

    @property
    def masked_api_key(self) -> str:
        """Returns a safe masked representation of the API key (never leaks the full secret)."""
        if not self.API_KEY:
            return "not-configured"
        if len(self.API_KEY) <= 8:
            return "configured (masked)"
        return f"{self.API_KEY[:4]}...{self.API_KEY[-4:]}"

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
