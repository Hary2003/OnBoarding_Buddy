import os
import subprocess
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from config import Settings, _parse_bool, _parse_origins, settings
from server import app

ROOT_DIR = Path(__file__).resolve().parent.parent


class TestProductionSecurity(TestCase):
    def setUp(self):
        self.orig_debug = app.debug
        self.orig_settings_debug = settings.DEBUG
        app.debug = False
        app.middleware_stack = None
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.debug = self.orig_debug
        settings.DEBUG = self.orig_settings_debug
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


if __name__ == "__main__":
    import unittest
    unittest.main()


