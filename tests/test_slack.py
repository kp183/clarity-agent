"""Tests for Slack integration stub."""

import pytest
from clarity.integrations.slack import SlackNotifier


@pytest.fixture
def notifier():
    return SlackNotifier(channel="#test-incidents")


class TestSlackNotifier:
    def test_send_alert_stub(self, notifier):
        result = notifier.send_alert(
            title="High Error Rate",
            severity="high",
            description="Error rate exceeded 25%",
            affected_services=["auth-service", "api-gateway"],
            actions=["Check logs", "Scale replicas"],
        )
        assert result["ok"] is True
        assert result["mode"] == "stub"
        assert "attachments" in result["payload"]

    def test_send_alert_with_webhook(self):
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test", channel="#prod")
        result = notifier.send_alert(
            title="Test Alert",
            severity="low",
            description="This is a test",
        )
        assert result["ok"] is True

    def test_send_incident_report(self, notifier):
        result = notifier.send_incident_report(
            report_markdown="## Incident Report\n\nSome details...",
            incident_id="INC-001",
        )
        assert result["ok"] is True
        blocks = result["payload"]["blocks"]
        assert any("Incident Report" in str(b) for b in blocks)

    def test_severity_color_mapping(self, notifier):
        for severity in ["low", "medium", "high", "critical"]:
            result = notifier.send_alert(
                title=f"{severity} alert",
                severity=severity,
                description="test",
            )
            assert result["ok"] is True


class TestSlackPayloadStructure:
    def test_alert_has_proper_blocks(self):
        notifier = SlackNotifier()
        result = notifier.send_alert(
            title="DB Down",
            severity="critical",
            description="Database unreachable",
            affected_services=["database"],
            actions=["Restart DB", "Check network"],
        )
        attachment = result["payload"]["attachments"][0]
        assert "color" in attachment
        assert len(attachment["blocks"]) >= 3  # header + fields + description + actions
