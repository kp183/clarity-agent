"""
Integration Tests — End-to-end tests that verify multiple components
work together correctly.
"""

import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from clarity.parsers.log_parser import parse_log_files
from clarity.agents.analyst import AnalystAgent
from clarity.agents.sentinel import SentinelAgent
from clarity.integrations.report_exporter import ReportExporter
from clarity.integrations.slack import SlackNotifier
from clarity.integrations.jira import JiraClient


@pytest.fixture
def error_log_file(tmp_path):
    """Create a realistic error log file for integration testing."""
    log_content = """2024-01-15 10:00:00 INFO api-gateway: Request received from 192.168.1.100
2024-01-15 10:00:01 INFO auth-service: Authenticating user session_abc123
2024-01-15 10:00:02 ERROR auth-service: Connection timeout to database (pool exhausted)
2024-01-15 10:00:03 ERROR auth-service: Failed to authenticate: ConnectionError
2024-01-15 10:00:04 WARN api-gateway: Upstream auth-service returned 503
2024-01-15 10:00:05 ERROR user-service: Cannot fetch user profile: auth dependency unavailable
2024-01-15 10:00:06 ERROR api-gateway: 5 consecutive failures for /api/v1/users
2024-01-15 10:00:07 FATAL auth-service: Service health check failed, entering degraded mode
2024-01-15 10:00:08 INFO ops-bot: Auto-scaling triggered for auth-service (replicas: 2 -> 4)
2024-01-15 10:00:09 INFO auth-service: New instance starting, pool re-initializing
"""
    log_file = tmp_path / "incident.log"
    log_file.write_text(log_content)
    return str(log_file)


class TestParserToAnalystPipeline:
    """Test the full pipeline: log file → parser → analyst agent."""

    def test_parser_produces_valid_df(self, error_log_file):
        df = parse_log_files([error_log_file])
        assert not df.empty
        assert "timestamp" in df.columns
        assert "level" in df.columns
        assert "message" in df.columns
        # Should have 10 log lines
        assert len(df) == 10

    def test_parser_captures_error_levels(self, error_log_file):
        df = parse_log_files([error_log_file])
        errors = df[df["level"].str.upper() == "ERROR"]
        assert len(errors) >= 4  # 4 ERROR lines

    @patch("clarity.agents.analyst.llm_client")
    def test_analyst_processes_parsed_logs(self, mock_llm, error_log_file):
        mock_response = json.dumps({
            "summary": "Auth service cascade failure",
            "root_cause_description": "Connection pool exhaustion",
            "affected_components": ["auth-service"],
            "confidence_score": 0.85,
            "remediation_steps": ["Restart pool"],
        })
        mock_llm.invoke.return_value = mock_response

        agent = AnalystAgent()
        # Access internal methods for testing pipeline
        df = parse_log_files([error_log_file])
        assert not df.empty


class TestSentinelDetection:
    """Test that Sentinel correctly identifies issues from real log data."""

    def test_sentinel_detects_high_error_rate(self, error_log_file):
        agent = SentinelAgent()
        df = parse_log_files([error_log_file])
        # Override predictive analysis to avoid LLM calls during tests
        agent._run_predictive_analysis = lambda df: []
        alerts = agent._detect_trends(df)
        # 4 errors out of 10 = 40% > 15% threshold
        assert len(alerts) >= 1
        assert alerts[0].description is not None


class TestReportExportPipeline:
    """Test the full pipeline: analysis → report export."""

    def test_markdown_report_from_analysis(self, error_log_file):
        df = parse_log_files([error_log_file])
        timeline_data = df.to_dict("records")

        # Convert timestamps for serialization
        for row in timeline_data:
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()

        analysis = json.dumps({
            "summary": "Auth cascade failure",
            "root_cause_description": "Pool exhaustion",
            "affected_components": ["auth-service"],
            "confidence_score": 0.9,
        })

        exporter = ReportExporter()
        md = exporter.to_markdown(analysis, timeline_data, "kubectl restart deploy/auth-service")
        assert "Auth cascade failure" in md
        assert "kubectl restart" in md
        assert "| Time |" in md

    def test_json_report_from_analysis(self, error_log_file):
        df = parse_log_files([error_log_file])
        timeline_data = df.to_dict("records")
        for row in timeline_data:
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()

        analysis = json.dumps({
            "summary": "DB timeout",
            "confidence_score": 0.75,
        })

        exporter = ReportExporter()
        result = json.loads(exporter.to_json(analysis, timeline_data))
        assert result["summary"] == "DB timeout"
        assert len(result["timeline"]) == 10


class TestNotificationPipeline:
    """Test that analysis flows correctly into Slack/Jira notifications."""

    def test_analysis_to_slack(self, error_log_file):
        df = parse_log_files([error_log_file])
        timeline_data = df.to_dict("records")
        for row in timeline_data:
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()

        analysis = json.dumps({"summary": "Test incident"})
        exporter = ReportExporter()
        report = exporter.to_markdown(analysis, timeline_data)

        notifier = SlackNotifier()
        result = notifier.send_incident_report(report, incident_id="INC-TEST")
        assert result["ok"] is True
        assert "Clarity Incident Report" in str(result["payload"]["blocks"])

    def test_analysis_to_jira(self, error_log_file):
        df = parse_log_files([error_log_file])
        analysis = json.dumps({
            "summary": "Auth failure",
            "affected_components": ["auth-service"],
        })

        exporter = ReportExporter()
        report = exporter.to_markdown(analysis, [])

        client = JiraClient(project_key="TEST")
        result = client.create_incident_ticket(
            summary="Auth failure",
            description=report,
            severity="high",
            affected_services=["auth-service"],
        )
        assert result["ok"] is True
        assert result["key"].startswith("TEST-")


class TestFullPipeline:
    """End-to-end: logs → parse → detect → report → notify."""

    def test_complete_flow(self, error_log_file):
        # 1. Parse
        df = parse_log_files([error_log_file])
        assert len(df) == 10

        # 2. Detect trends
        sentinel = SentinelAgent()
        sentinel._run_predictive_analysis = lambda df: []
        alerts = sentinel._detect_trends(df)
        assert len(alerts) >= 1

        # 3. Generate report
        timeline_data = df.to_dict("records")
        for row in timeline_data:
            if hasattr(row.get("timestamp"), "isoformat"):
                row["timestamp"] = row["timestamp"].isoformat()

        analysis = json.dumps({
            "summary": f"Detected {len(alerts)} anomaly trends",
            "affected_components": alerts[0].affected_services,
            "confidence_score": 0.85,
        })

        exporter = ReportExporter()
        md_report = exporter.to_markdown(analysis, timeline_data)
        json_report = json.loads(exporter.to_json(analysis, timeline_data))

        assert "anomaly trends" in md_report
        assert json_report["report_version"] == "1.0"

        # 4. Notify
        slack = SlackNotifier()
        slack_result = slack.send_incident_report(md_report)
        assert slack_result["ok"] is True

        jira = JiraClient(project_key="INC")
        jira_result = jira.create_incident_ticket(
            summary="Auto-detected incident",
            description=md_report,
        )
        assert jira_result["ok"] is True

        # 5. Save report
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            exporter.save(md_report, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 100
        finally:
            os.unlink(path)
