"""Tests for Clarity MCP server endpoints."""

import pytest
import httpx

from clarity.mcp.server import mcp_app


@pytest.fixture
def transport():
    return httpx.ASGITransport(app=mcp_app)


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
class TestToolsList:
    async def test_list_tools(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/tools")
            assert resp.status_code == 200
            tools = resp.json()["tools"]
            names = [t["name"] for t in tools]
            assert "rollback" in names
            assert "restart" in names
            assert "scale" in names
            assert "validate" in names


@pytest.mark.asyncio
class TestRollback:
    async def test_rollback_command(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/rollback", json={"service_name": "auth-service"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["tool"] == "rollback"
            assert "kubectl rollout undo" in data["command"]
            assert "auth-service" in data["command"]

    async def test_rollback_with_namespace(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/rollback", json={"service_name": "api-service", "namespace": "production"})
            assert resp.status_code == 200
            assert "production" in resp.json()["command"]

    async def test_rollback_empty_name(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/rollback", json={"service_name": ""})
            assert resp.status_code == 400

    async def test_rollback_sanitizes_input(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/rollback", json={"service_name": "auth; rm -rf /"})
            assert resp.status_code == 200
            cmd = resp.json()["command"]
            assert ";" not in cmd
            assert "authrm-rf" in cmd


@pytest.mark.asyncio
class TestRestart:
    async def test_restart_command(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/restart", json={"service_name": "user-service"})
            assert resp.status_code == 200
            assert "kubectl rollout restart" in resp.json()["command"]

    async def test_restart_empty_name(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/restart", json={"service_name": ""})
            assert resp.status_code == 400


@pytest.mark.asyncio
class TestScale:
    async def test_scale_command(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/scale", json={"service_name": "api-service", "replicas": 5})
            assert resp.status_code == 200
            data = resp.json()
            assert "--replicas=5" in data["command"]
            assert data["replicas"] == 5

    async def test_scale_zero_replicas(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/scale", json={"service_name": "api-service", "replicas": 0})
            assert resp.status_code == 200

    async def test_scale_negative_replicas(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/scale", json={"service_name": "api-service", "replicas": -1})
            assert resp.status_code == 400

    async def test_scale_empty_name(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/scale", json={"service_name": "", "replicas": 3})
            assert resp.status_code == 400


@pytest.mark.asyncio
class TestValidate:
    async def test_known_service(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/validate", json={"service_name": "auth-service"})
            assert resp.status_code == 200
            assert resp.json()["exists"] is True

    async def test_unknown_service(self, transport):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/tools/validate", json={"service_name": "mystery-service"})
            assert resp.status_code == 200
            assert resp.json()["exists"] is False
