"""Tests for container runtime configuration."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dockerignore_excludes_local_runtime_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text().splitlines()

    assert ".venv/" in dockerignore
    assert "uv.lock" in dockerignore
    assert ".pytest_cache/" in dockerignore


def test_dockerfile_uses_project_dependencies_and_healthcheck():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "DEBIAN_FRONTEND=noninteractive" in dockerfile
    assert "COPY pyproject.toml README.md /app/" in dockerfile
    assert 'pip install --prefer-binary ".[web]"' in dockerfile
    assert "playwright install --with-deps chromium" in dockerfile
    assert "| tail" not in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "127.0.0.1:8000/health" in dockerfile


def test_compose_keeps_init_enabled_and_passes_optional_tokens():
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "init: true" in compose
    assert "DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN:-}" in compose
