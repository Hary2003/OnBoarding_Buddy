"""
Automated validation tests for Frontend Dockerization and Docker Compose orchestration.
Verifies Dockerfile specifications, Nginx reverse proxy configuration, security headers,
and Docker Compose service dependencies.
"""

import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


class TestFrontendDockerConfig(unittest.TestCase):
    """Test suite validating frontend Docker assets and Nginx configuration."""

    def test_frontend_dockerfile_exists_and_configured(self):
        """Verify frontend/Dockerfile exists and contains required production directives."""
        dockerfile = FRONTEND_DIR / "Dockerfile"
        self.assertTrue(dockerfile.exists(), "frontend/Dockerfile must exist")

        content = dockerfile.read_text(encoding="utf-8")
        self.assertIn("FROM nginx:", content, "Should use official Nginx base image")
        self.assertIn("alpine", content, "Should use lightweight Alpine distribution")
        self.assertIn("EXPOSE 80", content, "Should expose standard HTTP port 80")
        self.assertIn("HEALTHCHECK", content, "Should define container HEALTHCHECK")
        self.assertIn("nginx.conf", content, "Should copy custom Nginx configuration")
        self.assertIn("index.html", content, "Should copy frontend assets")
        self.assertIn("style.css", content, "Should copy styles")
        self.assertIn("app.js", content, "Should copy JavaScript application")

    def test_frontend_nginx_conf_security_and_proxy(self):
        """Verify frontend/nginx.conf defines security headers and reverse proxies."""
        nginx_conf = FRONTEND_DIR / "nginx.conf"
        self.assertTrue(nginx_conf.exists(), "frontend/nginx.conf must exist")

        content = nginx_conf.read_text(encoding="utf-8")
        # Security headers
        self.assertIn("X-Frame-Options", content, "Must configure X-Frame-Options header")
        self.assertIn("X-Content-Type-Options", content, "Must configure X-Content-Type-Options nosniff")
        self.assertIn("nosniff", content)
        self.assertIn("X-XSS-Protection", content, "Must configure X-XSS-Protection")

        # Reverse proxy routing
        self.assertIn("location /api/", content, "Must route /api/ to backend")
        self.assertIn("backend:8000", content, "Must proxy to backend:8000")
        self.assertIn("proxy_pass", content)

        # Healthcheck endpoint
        self.assertIn("location = /healthz", content, "Must provide dedicated /healthz endpoint")
        self.assertIn("healthy", content)

        # Static assets and SPA handling
        self.assertIn("location /static/", content, "Must map /static/ asset paths")
        self.assertIn("gzip on;", content, "Must enable gzip compression")
        self.assertIn("try_files", content, "Must support SPA fallback")

    def test_frontend_dockerignore(self):
        """Verify frontend/.dockerignore excludes build and development noise."""
        dockerignore = FRONTEND_DIR / ".dockerignore"
        self.assertTrue(dockerignore.exists(), "frontend/.dockerignore must exist")

        content = dockerignore.read_text(encoding="utf-8")
        self.assertIn("node_modules/", content)
        self.assertIn(".git/", content)

    def test_frontend_vite_tooling(self):
        """Verify Vite configuration files exist for local frontend development."""
        pkg_json = FRONTEND_DIR / "package.json"
        vite_conf = FRONTEND_DIR / "vite.config.js"

        self.assertTrue(pkg_json.exists(), "frontend/package.json must exist")
        self.assertTrue(vite_conf.exists(), "frontend/vite.config.js must exist")

        pkg_content = pkg_json.read_text(encoding="utf-8")
        self.assertIn('"vite"', pkg_content, "package.json must reference Vite")
        self.assertIn('"dev": "vite"', pkg_content)

        vite_content = vite_conf.read_text(encoding="utf-8")
        self.assertIn("defineConfig", vite_content)
        self.assertIn("/api", vite_content, "Vite config must proxy /api to backend")

    def test_docker_compose_orchestration(self):
        """Verify root docker-compose.yml defines backend and frontend services."""
        compose_file = ROOT_DIR / "docker-compose.yml"
        self.assertTrue(compose_file.exists(), "docker-compose.yml must exist at repository root")

        content = compose_file.read_text(encoding="utf-8")
        # Services definition
        self.assertIn("backend:", content)
        self.assertIn("frontend:", content)

        # Port mapping
        self.assertIn("3000:80", content, "Frontend should expose port 3000 (mapped to container 80)")
        self.assertIn("8000:8000", content, "Backend should expose port 8000")

        # Dependency and health checks
        self.assertIn("service_healthy", content, "Frontend should depend on healthy backend")
        self.assertIn("healthcheck:", content)
        self.assertIn("onboarding-network", content, "Services should share network")

    def test_docker_compose_dev_override(self):
        """Verify docker-compose.dev.yml exists for live development mounting."""
        compose_dev = ROOT_DIR / "docker-compose.dev.yml"
        self.assertTrue(compose_dev.exists(), "docker-compose.dev.yml should exist")

        content = compose_dev.read_text(encoding="utf-8")
        self.assertIn("services:", content)
        self.assertIn("backend:", content)
        self.assertIn("frontend:", content)


if __name__ == "__main__":
    unittest.main()
