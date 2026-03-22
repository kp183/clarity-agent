"""
Tests for JWT middleware in clarity/api/server.py (Requirement 13.7).
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from clarity.api.server import app, verify_token
from clarity.config import settings


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_token():
    """Generate a valid HS256 JWT for testing."""
    from jose import jwt
    return jwt.encode({"sub": "test-user"}, "test-secret", algorithm="HS256")


# ── Health check is always public ────────────────────────────────────────────

def test_health_no_auth_required(client):
    """GET /health must be accessible without any token."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_with_auth_enabled_still_accessible(client):
    """GET /health must remain accessible even when auth is enabled."""
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.get("/health")
    assert resp.status_code == 200


# ── Auth disabled (default) ───────────────────────────────────────────────────

def test_protected_route_no_token_auth_disabled(client):
    """When AUTH_ENABLED=False, routes work without a token."""
    with patch.object(settings, "auth_enabled", False):
        # /ticket requires prior analysis state; 400 means auth passed, logic failed
        resp = client.post("/ticket")
    assert resp.status_code != 401


# ── Auth enabled — missing token ──────────────────────────────────────────────

def test_missing_token_returns_401(client):
    """When AUTH_ENABLED=True and no token is provided, expect 401."""
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.post("/ticket")
    assert resp.status_code == 401


def test_missing_token_on_analyze_returns_401(client):
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.post("/analyze")
    assert resp.status_code == 401


def test_missing_token_on_chat_returns_401(client):
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.post("/copilot/chat", json={"message": "hello"})
    assert resp.status_code == 401


def test_missing_token_on_monitoring_returns_401(client):
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.get("/monitoring/status")
    assert resp.status_code == 401


# ── Auth enabled — invalid token ──────────────────────────────────────────────

def test_invalid_token_returns_401(client):
    """A garbage Bearer token must return 401."""
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.post("/ticket", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


def test_wrong_secret_returns_401(client, valid_token):
    """A token signed with the wrong secret must return 401."""
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "different-secret"):
        resp = client.post("/ticket", headers={"Authorization": f"Bearer {valid_token}"})
    assert resp.status_code == 401


# ── Auth enabled — valid token ────────────────────────────────────────────────

def test_valid_token_passes_auth(client, valid_token):
    """A valid JWT must pass auth (route may return 400 for missing state, not 401)."""
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.post("/ticket", headers={"Authorization": f"Bearer {valid_token}"})
    # 400 = auth passed, no analysis state available — that's fine
    assert resp.status_code != 401


def test_valid_token_on_monitoring(client, valid_token):
    with patch.object(settings, "auth_enabled", True), \
         patch.object(settings, "jwt_secret_key", "test-secret"):
        resp = client.get("/monitoring/status", headers={"Authorization": f"Bearer {valid_token}"})
    assert resp.status_code != 401
