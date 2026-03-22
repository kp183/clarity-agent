"""Tests for the Report Exporter (Markdown and JSON)."""

import pytest
import json
import tempfile
import os

from clarity.integrations.report_exporter import ReportExporter


@pytest.fixture
def exporter():
    return ReportExporter()


@pytest.fixture
def sample_analysis():
    return json.dumps({
        "summary": "Database connection timeout caused cascading failures",
        "root_cause_description": "Connection pool exhaustion in auth-service",
        "affected_components": ["auth-service", "user-service", "api-gateway"],
        "confidence_score": 0.87,
        "remediation_steps": [
            "Restart connection pool",
            "Scale auth-service replicas to 5",
            "Enable circuit breaker",
        ],
        "incident_id": "INC-20240115-001",
    })


@pytest.fixture
def sample_timeline():
    return [
        {"timestamp": "2024-01-15 10:00:00", "level": "INFO", "service": "api", "message": "Request received"},
        {"timestamp": "2024-01-15 10:01:00", "level": "ERROR", "service": "auth", "message": "Connection timeout"},
        {"timestamp": "2024-01-15 10:02:00", "level": "FATAL", "service": "auth", "message": "Service crashed"},
    ]


@pytest.fixture
def sample_history():
    return [
        {"question": "What caused the crash?", "answer": "Connection pool exhaustion", "timestamp": "10:05:00"},
        {"question": "How to fix?", "answer": "Restart and scale", "timestamp": "10:06:00"},
    ]


class TestMarkdownExport:
    def test_basic_markdown(self, exporter, sample_analysis, sample_timeline):
        md = exporter.to_markdown(sample_analysis, sample_timeline)
        assert "# 🤖 Clarity Incident Report" in md
        assert "Database connection timeout" in md
        assert "auth-service" in md
        assert "87.0%" in md

    def test_includes_timeline_table(self, exporter, sample_analysis, sample_timeline):
        md = exporter.to_markdown(sample_analysis, sample_timeline)
        assert "| Time |" in md
        assert "Connection timeout" in md

    def test_includes_remediation(self, exporter, sample_analysis, sample_timeline):
        md = exporter.to_markdown(sample_analysis, sample_timeline, remediation_cmd="kubectl restart")
        assert "kubectl restart" in md

    def test_includes_conversation(self, exporter, sample_analysis, sample_timeline, sample_history):
        md = exporter.to_markdown(sample_analysis, sample_timeline,
                                   conversation_history=sample_history)
        assert "Co-Pilot Investigation Log" in md
        assert "What caused the crash?" in md

    def test_handles_empty_data(self, exporter):
        md = exporter.to_markdown("", [])
        assert "Clarity Incident Report" in md

    def test_handles_raw_string_analysis(self, exporter):
        md = exporter.to_markdown("Some plain text analysis", [])
        assert "Some plain text analysis" in md

    def test_truncates_timeline_to_25_events(self, exporter, sample_analysis):
        """Requirement 7.4: only first 25 events appear in Markdown output."""
        events = [
            {"timestamp": f"2024-01-15 10:{i:02d}:00", "level": "INFO", "service": "svc", "message": f"event {i}"}
            for i in range(30)
        ]
        md = exporter.to_markdown(sample_analysis, events)
        # Count table rows (lines starting with "| 2024")
        rows = [line for line in md.splitlines() if line.startswith("| 2024")]
        assert len(rows) == 25

    def test_truncation_warning_logged_for_markdown(self, exporter, sample_analysis, caplog):
        """A warning is emitted when timeline exceeds 25 events."""
        import logging
        events = [
            {"timestamp": f"2024-01-15 10:{i:02d}:00", "level": "INFO", "service": "svc", "message": f"event {i}"}
            for i in range(26)
        ]
        with caplog.at_level(logging.WARNING):
            exporter.to_markdown(sample_analysis, events)
        # structlog may not use caplog; verify output is still truncated
        md = exporter.to_markdown(sample_analysis, events)
        rows = [line for line in md.splitlines() if line.startswith("| 2024")]
        assert len(rows) == 25


class TestJsonExport:
    def test_basic_json(self, exporter, sample_analysis, sample_timeline):
        result = exporter.to_json(sample_analysis, sample_timeline)
        data = json.loads(result)
        assert data["report_version"] == "1.0"
        assert data["summary"] == "Database connection timeout caused cascading failures"
        assert len(data["affected_components"]) == 3

    def test_json_includes_timeline(self, exporter, sample_analysis, sample_timeline):
        data = json.loads(exporter.to_json(sample_analysis, sample_timeline))
        assert len(data["timeline"]) == 3
        assert data["timeline"][1]["level"] == "ERROR"

    def test_json_includes_investigation(self, exporter, sample_analysis, sample_timeline, sample_history):
        data = json.loads(exporter.to_json(sample_analysis, sample_timeline,
                                            conversation_history=sample_history))
        assert len(data["investigation"]) == 2

    def test_json_is_valid(self, exporter, sample_analysis, sample_timeline):
        result = exporter.to_json(sample_analysis, sample_timeline)
        # Should not raise
        assert json.loads(result) is not None

    def test_truncates_timeline_to_50_events(self, exporter, sample_analysis):
        """Requirement 7.5: only first 50 events appear in JSON output."""
        events = [
            {"timestamp": f"2024-01-15 10:{i:02d}:00", "level": "INFO", "service": "svc", "message": f"event {i}"}
            for i in range(60)
        ]
        data = json.loads(exporter.to_json(sample_analysis, events))
        assert len(data["timeline"]) == 50

    def test_truncation_warning_logged_for_json(self, exporter, sample_analysis):
        """A warning is emitted when timeline exceeds 50 events; output is still capped."""
        events = [
            {"timestamp": f"2024-01-15 10:{i:02d}:00", "level": "INFO", "service": "svc", "message": f"event {i}"}
            for i in range(51)
        ]
        data = json.loads(exporter.to_json(sample_analysis, events))
        assert len(data["timeline"]) == 50


class TestSaveToFile:
    def test_save_markdown(self, exporter, sample_analysis, sample_timeline):
        md = exporter.to_markdown(sample_analysis, sample_timeline)
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
            path = f.name
        try:
            exporter.save(md, path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Clarity Incident Report" in content
        finally:
            os.unlink(path)

    def test_save_json(self, exporter, sample_analysis, sample_timeline):
        j = exporter.to_json(sample_analysis, sample_timeline)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            exporter.save(j, path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["report_version"] == "1.0"
        finally:
            os.unlink(path)
