"""Tests for Jira integration stub."""

import pytest
from clarity.integrations.jira import JiraClient


@pytest.fixture
def client():
    return JiraClient(project_key="TEST")


class TestJiraClient:
    def test_create_ticket_stub(self, client):
        result = client.create_incident_ticket(
            summary="Auth service outage",
            description="Connection pool exhausted",
            severity="high",
            affected_services=["auth-service", "user-service"],
            remediation_steps=["Restart connection pool", "Scale replicas"],
        )
        assert result["ok"] is True
        assert result["mode"] == "stub"
        assert result["key"].startswith("TEST-")
        assert "[Clarity]" in result["payload"]["fields"]["summary"]

    def test_ticket_priority_mapping(self, client):
        for severity, expected in [("low", "Low"), ("medium", "Medium"),
                                    ("high", "High"), ("critical", "Highest")]:
            result = client.create_incident_ticket(
                summary=f"{severity} test",
                description="test",
                severity=severity,
            )
            assert result["payload"]["fields"]["priority"]["name"] == expected

    def test_ticket_has_labels(self, client):
        result = client.create_incident_ticket(
            summary="Test",
            description="Test desc",
        )
        labels = result["payload"]["fields"]["labels"]
        assert "clarity-ai" in labels
        assert "auto-generated" in labels

    def test_update_ticket(self, client):
        result = client.update_ticket("TEST-123", "Incident resolved after restart.")
        assert result["ok"] is True
        assert "Clarity AI Update" in result["payload"]["comment"]["body"]

    def test_custom_labels(self, client):
        result = client.create_incident_ticket(
            summary="Custom",
            description="desc",
            labels=["p0", "production"],
        )
        assert result["payload"]["fields"]["labels"] == ["p0", "production"]

    def test_connected_mode(self):
        client = JiraClient(
            base_url="https://myorg.atlassian.net",
            email="test@test.com",
            api_token="token123",
        )
        result = client.create_incident_ticket(
            summary="Live test",
            description="desc",
        )
        assert result["ok"] is True
