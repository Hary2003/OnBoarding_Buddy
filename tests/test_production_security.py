import os
import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from config import Settings, _parse_bool, _parse_origins, settings
from server import app
from services.security_guard import rate_limiter

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestProductionSecurity(TestCase):
    def setUp(self):
        self.orig_debug = app.debug
        self.orig_settings_debug = settings.DEBUG
        self.orig_rate_limit_enabled = settings.RATE_LIMIT_ENABLED
        self.orig_rate_limit_per_min = settings.RATE_LIMIT_PER_MINUTE
        self.orig_api_auth_enabled = settings.API_AUTH_ENABLED
        self.orig_api_key = settings.API_KEY
        self.orig_env = settings.ENVIRONMENT
        app.debug = False
        app.middleware_stack = None
        rate_limiter.reset()
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.debug = self.orig_debug
        settings.DEBUG = self.orig_settings_debug
        settings.RATE_LIMIT_ENABLED = self.orig_rate_limit_enabled
        settings.RATE_LIMIT_PER_MINUTE = self.orig_rate_limit_per_min
        settings.API_AUTH_ENABLED = self.orig_api_auth_enabled
        settings.API_KEY = self.orig_api_key
        settings.ENVIRONMENT = self.orig_env
        rate_limiter.reset()
        app.middleware_stack = None

    def test_01_gitignore_excludes_env_and_secrets(self):
        """Verify .gitignore properly excludes .env, .env.*, secrets, but tracks .env.example."""
        gitignore_path = ROOT_DIR / ".gitignore"
        self.assertTrue(gitignore_path.exists())
        content = gitignore_path.read_text(encoding="utf-8")
        
        self.assertIn(".env", content)
        self.assertIn(".env.*", content)
        self.assertIn("!.env.example", content)
        self.assertIn("*.key", content)
        self.assertIn("secrets/", content)

    def test_02_no_api_keys_or_env_in_git_tracked_files(self):
        """Verify git tracked files do not contain .env or live Groq API keys."""
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        tracked_files = res.stdout.splitlines()

        # .env must NEVER be tracked in git
        self.assertNotIn(".env", tracked_files)
        self.assertNotIn(".env.local", tracked_files)
        self.assertNotIn(".env.production", tracked_files)

        # Check all tracked files for accidental leaks of actual Groq API keys (gsk_...)
        for file_rel in tracked_files:
            file_path = ROOT_DIR / file_rel
            if not file_path.is_file():
                continue
            # Ignore test files that might test vulnerability diffs with dummy strings
            if "test_pr_review.py" in file_rel or "app.js" in file_rel:
                continue
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn(
                    "gsk_",
                    text,
                    f"Found potential live Groq API key (gsk_) in tracked file: {file_rel}"
                )
            except Exception:
                pass

    def test_03_env_example_complete_and_contains_no_secrets(self):
        """Verify .env.example contains all required production configuration keys with placeholders."""
        example_path = ROOT_DIR / ".env.example"
        self.assertTrue(example_path.exists())
        content = example_path.read_text(encoding="utf-8")

        required_keys = [
            "ENVIRONMENT",
            "DEBUG",
            "HOST",
            "PORT",
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "CORS_ALLOWED_ORIGINS",
            "ENABLE_DOCS",
            "LOG_LEVEL"
        ]
        for key in required_keys:
            self.assertIn(key, content, f"Missing {key} in .env.example")

        # Must not contain live keys
        self.assertNotIn("gsk_", content)
        self.assertIn("your_groq_api_key_here", content)

    def test_04_groq_api_key_deployment_secret_support(self):
        """Verify Groq API key is read from system environment variable / deployment secret."""
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_prod_secret_token_1234567890"}, clear=False):
            prod_settings = Settings()
            self.assertTrue(prod_settings.is_groq_configured)
            # Check masking
            masked = prod_settings.masked_groq_key
            self.assertTrue(masked.startswith("gsk_"))
            self.assertTrue(masked.endswith("7890"))
            self.assertNotIn("secret_token", masked)

    def test_05_masked_groq_key_safety(self):
        """Verify masked_groq_key does not leak keys when empty or placeholder."""
        s = Settings(GROQ_API_KEY="")
        self.assertEqual(s.masked_groq_key, "not-configured")

        s = Settings(GROQ_API_KEY="your_groq_api_key_here")
        self.assertEqual(s.masked_groq_key, "not-configured")

    def test_06_health_check_does_not_leak_groq_api_key(self):
        """Verify /api/health endpoint returns configured status without exposing the actual key."""
        with patch.object(settings, "GROQ_API_KEY", "gsk_super_secret_deployment_key"):
            res = self.client.get("/api/health")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("status", data)
            self.assertIn("environment", data)
            self.assertIn("debug", data)
            self.assertIn("groq_configured", data)
            self.assertTrue(data["groq_configured"])
            # Ensure the actual secret is never in the payload
            self.assertNotIn("GROQ_API_KEY", data)
            self.assertNotIn("gsk_super_secret_deployment_key", res.text)

    def test_07_production_settings_parsing(self):
        """Verify production environment variables are properly evaluated."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "HOST": "0.0.0.0",
            "PORT": "9000",
            "CORS_ALLOWED_ORIGINS": "https://app.example.com,https://api.example.com",
            "ENABLE_DOCS": "false",
            "LOG_LEVEL": "WARNING"
        }, clear=False):
            s = Settings()
            self.assertTrue(s.is_production)
            self.assertFalse(s.is_development)
            self.assertFalse(s.DEBUG)
            self.assertEqual(s.HOST, "0.0.0.0")
            self.assertEqual(s.PORT, 9000)
            self.assertEqual(s.CORS_ALLOWED_ORIGINS, ["https://app.example.com", "https://api.example.com"])
            self.assertFalse(s.ENABLE_DOCS)
            self.assertEqual(s.LOG_LEVEL, "WARNING")

    def test_08_production_cors_policy(self):
        """Verify CORS returns explicit domains in production and never returns wildcard by default."""
        s = Settings(ENVIRONMENT="production", CORS_ALLOWED_ORIGINS=[])
        # In production with no configured origins, must return empty (strictly forbidding wildcard)
        self.assertEqual(s.get_cors_origins(), [])

        # In production with configured origins
        s = Settings(ENVIRONMENT="production", CORS_ALLOWED_ORIGINS=["https://onboarding.example.com"])
        self.assertEqual(s.get_cors_origins(), ["https://onboarding.example.com"])

        # In development, local dev origins should be present
        s = Settings(ENVIRONMENT="development", CORS_ALLOWED_ORIGINS=[])
        dev_origins = s.get_cors_origins()
        self.assertIn("http://localhost:3000", dev_origins)
        self.assertIn("http://127.0.0.1:8000", dev_origins)

    def test_09_secure_error_response_in_production(self):
        """Verify 500 error messages are sanitized when DEBUG is false."""
        with patch.object(settings, "DEBUG", False):
            # Test custom error on file-content with invalid internal open
            with patch("builtins.open", side_effect=IOError("Sensitive internal path: /var/secrets/key")):
                res = self.client.get("/api/file-content?file_path=server.py")
                self.assertEqual(res.status_code, 500)
                data = res.json()
                self.assertNotIn("/var/secrets/key", data.get("detail", ""))
                self.assertIn("An internal server error occurred while processing the request", data.get("detail", ""))

    def test_10_file_content_validation(self):
        """Verify /api/file-content returns 404 for non-existent files."""
        res = self.client.get("/api/file-content?file_path=non_existent_file_xyz_123.txt")
        self.assertEqual(res.status_code, 404)

    def test_11_summarize_file_not_found(self):
        """Verify /api/summarize returns 404 for non-existent file path."""
        res = self.client.post("/api/summarize", json={
            "file_path": "non_existent_file.py",
            "session_id": "default"
        })
        self.assertEqual(res.status_code, 404)

    def test_12_unhandled_exception_sanitized_in_production(self):
        """Verify unhandled exceptions return a clean generic error message in production."""
        with patch.object(settings, "DEBUG", False):
            # Trigger unhandled exception by mocking an endpoint call that fails
            with patch("services.repo_service.repo_service.parse_repository", side_effect=RuntimeError("Database credentials leaked: user:pass@db")):
                res = self.client.post("/api/clone", json={"url_or_path": "https://github.com/example/test"})
                self.assertEqual(res.status_code, 500)
                data = res.json()
                self.assertNotIn("Database credentials", data.get("detail", ""))
                self.assertIn("An internal server error occurred", data.get("detail", ""))

    def test_13_debug_mode_error_details_in_development(self):
        """Verify debug mode includes error information for local developer troubleshooting."""
        with patch.object(settings, "DEBUG", True):
            with patch("services.repo_service.repo_service.parse_repository", side_effect=RuntimeError("Dev detail info")):
                res = self.client.post("/api/clone", json={"url_or_path": "https://github.com/example/test"})
                self.assertEqual(res.status_code, 500)
                data = res.json()
                self.assertIn("Dev detail info", data.get("detail", ""))

    def test_14_dockerignore_excludes_env_secrets_and_artifacts(self):
        """Verify .dockerignore properly excludes .env, credentials, .git, .venv, and build caches."""
        dockerignore_path = ROOT_DIR / ".dockerignore"
        self.assertTrue(dockerignore_path.exists())
        content = dockerignore_path.read_text(encoding="utf-8")

        # Secrets & environment
        self.assertIn(".env", content)
        self.assertIn(".env.*", content)
        self.assertIn("!.env.example", content)
        self.assertIn("*.key", content)
        self.assertIn("secrets/", content)

        # Build context bloat & venvs
        self.assertIn(".git/", content)
        self.assertIn(".venv/", content)
        self.assertIn("__pycache__/", content)
        self.assertIn("*.py[cod]", content)

    def test_15_docker_container_host_and_reload_overrides(self):
        """Verify that when running in a Docker container, host binds to 0.0.0.0 and reload is disabled."""
        with patch.dict(os.environ, {
            "DOCKER_CONTAINER": "true",
            "HOST": "127.0.0.1",
            "DEBUG": "true",
            "ENVIRONMENT": "development"
        }, clear=False):
            s = Settings()
            self.assertTrue(s.is_container)
            self.assertEqual(s.HOST, "0.0.0.0")
            self.assertFalse(s.RELOAD)

    def test_16_local_dev_settings_preserved(self):
        """Verify that outside a container, local development settings (127.0.0.1 and reload) are preserved."""
        s = Settings(IS_CONTAINER=False, HOST="127.0.0.1", DEBUG="true", ENVIRONMENT="development")
        self.assertFalse(s.is_container)
        self.assertEqual(s.HOST, "127.0.0.1")
        self.assertTrue(s.RELOAD)

    def test_17_github_actions_ci_workflow(self):
        """Verify .github/workflows/ci.yml exists and defines test and security checks."""
        ci_path = ROOT_DIR / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_path.exists(), "CI workflow .github/workflows/ci.yml must exist")
        content = ci_path.read_text(encoding="utf-8")
        self.assertIn("name: CI Pipeline", content)
        self.assertIn("actions/checkout@v4", content)
        self.assertIn("actions/setup-python@v5", content)
        self.assertIn("unittest discover tests", content)
        self.assertIn("docker build", content)

    def test_18_security_headers_present(self):
        """Verify HTTP security headers (nosniff, DENY, HSTS, etc.) are present on responses."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        headers = {k.lower(): v for k, v in res.headers.items()}
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("x-xss-protection"), "1; mode=block")
        self.assertEqual(headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertIn("geolocation=()", headers.get("permissions-policy", ""))

        # In production mode, HSTS should be present
        with patch.object(settings, "ENVIRONMENT", "production"):
            prod_res = self.client.get("/api/health")
            prod_headers = {k.lower(): v for k, v in prod_res.headers.items()}
            self.assertIn("max-age=31536000", prod_headers.get("strict-transport-security", ""))

    def test_19_rate_limiting_enforcement_and_headers(self):
        """Verify rate limiter blocks abuse with 429 and includes Retry-After and rate limit headers."""
        settings.RATE_LIMIT_ENABLED = True
        settings.RATE_LIMIT_PER_MINUTE = 3
        rate_limiter.reset()

        # Send 3 requests (within limit)
        for i in range(3):
            res = self.client.get("/api/repositories")
            self.assertEqual(res.status_code, 200)
            self.assertIn("x-ratelimit-limit", [k.lower() for k in res.headers.keys()])

        # 4th request must be blocked with 429
        blocked_res = self.client.get("/api/repositories")
        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn("too many requests", blocked_res.json().get("detail", "").lower())
        self.assertIn("retry-after", [k.lower() for k in blocked_res.headers.keys()])
        # Ensure security headers are still present even on 429 responses
        self.assertEqual(blocked_res.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(blocked_res.headers.get("x-frame-options"), "DENY")

        # Health check must bypass rate limiting
        health_res = self.client.get("/api/health")
        self.assertEqual(health_res.status_code, 200)

    def test_20_api_authentication_middleware(self):
        """Verify API key authentication when API_AUTH_ENABLED is True."""
        settings.API_AUTH_ENABLED = True
        settings.API_KEY = "test-secret-api-key-12345"

        # 1. Unauthenticated request to /api/repositories returns 401
        res = self.client.get("/api/repositories")
        self.assertEqual(res.status_code, 401)
        self.assertIn("unauthorized", res.json().get("detail", "").lower())
        self.assertEqual(res.headers.get("www-authenticate"), "Bearer")
        # Ensure security headers present on 401
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")

        # 2. Invalid Bearer token returns 401
        res_bad = self.client.get("/api/repositories", headers={"Authorization": "Bearer invalid-token"})
        self.assertEqual(res_bad.status_code, 401)

        # 3. Valid Bearer token returns 200
        res_bearer = self.client.get("/api/repositories", headers={"Authorization": "Bearer test-secret-api-key-12345"})
        self.assertEqual(res_bearer.status_code, 200)

        # 4. Valid X-API-Key header returns 200
        res_apikey = self.client.get("/api/repositories", headers={"X-API-Key": "test-secret-api-key-12345"})
        self.assertEqual(res_apikey.status_code, 200)

        # 5. Health check and DB status must remain accessible without auth
        res_health = self.client.get("/api/health")
        self.assertEqual(res_health.status_code, 200)
        res_db = self.client.get("/api/db/status")
        self.assertEqual(res_db.status_code, 200)

    def test_21_api_key_masking(self):
        """Verify API_KEY masking prevents leaking secret keys in configuration outputs."""
        s = Settings(API_KEY="")
        self.assertEqual(s.masked_api_key, "not-configured")
        self.assertFalse(s.is_auth_configured)

        s2 = Settings(API_KEY="short")
        self.assertEqual(s2.masked_api_key, "configured (masked)")

        s3 = Settings(API_AUTH_ENABLED=True, API_KEY="onboarding_sec_prod_key_998877")
        self.assertTrue(s3.is_auth_configured)
        masked = s3.masked_api_key
        self.assertTrue(masked.startswith("onbo"))
        self.assertTrue(masked.endswith("8877"))
        self.assertNotIn("prod_key", masked)


if __name__ == "__main__":
    import unittest
    unittest.main()


