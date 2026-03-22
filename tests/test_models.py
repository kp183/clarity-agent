"""Tests for Clarity Pydantic models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from clarity.core.models import (
    LogLevel,
    TrendType,
    AlertSeverity,
    LogEvent,
    RootCause,
    RemediationCommand,
    AnalysisResult,
    TrendAnalysis,
    ProactiveAlert,
    MonitoringResult,
)


class TestLogEvent:
    def test_creates_valid_event(self):
        event = LogEvent(
            timestamp=datetime.now(),
            level="ERROR",
            service="auth-service",
            message="Connection failed",
        )
        assert event.level == "ERROR"
        assert event.service == "auth-service"

    def test_defaults(self):
        event = LogEvent(timestamp=datetime.now(), message="test")
        assert event.level == "INFO"
        assert event.service == "unknown"
        assert event.metadata == {}


class TestRootCause:
    def test_valid_confidence(self):
        rc = RootCause(
            summary="DB failure",
            description="Connection pool exhausted",
            affected_components=["database"],
            confidence_score=0.85,
        )
        assert rc.confidence_score == 0.85

    def test_rejects_confidence_over_1(self):
        with pytest.raises(ValidationError):
            RootCause(
                summary="test",
                description="test",
                affected_components=[],
                confidence_score=1.5,
            )

    def test_rejects_negative_confidence(self):
        with pytest.raises(ValidationError):
            RootCause(
                summary="test",
                description="test",
                affected_components=[],
                confidence_score=-0.1,
            )

    def test_boundary_values(self):
        rc0 = RootCause(summary="t", description="t", affected_components=[], confidence_score=0.0)
        rc1 = RootCause(summary="t", description="t", affected_components=[], confidence_score=1.0)
        assert rc0.confidence_score == 0.0
        assert rc1.confidence_score == 1.0


class TestAnalysisResult:
    def test_generates_unique_ids(self):
        r1 = AnalysisResult()
        r2 = AnalysisResult()
        assert r1.incident_id != r2.incident_id

    def test_incident_id_format(self):
        result = AnalysisResult()
        assert result.incident_id.startswith("INC-")

    def test_defaults(self):
        result = AnalysisResult()
        assert result.timeline == []
        assert result.root_cause is None
        assert result.events_processed == 0


class TestProactiveAlert:
    def test_unique_alert_ids(self):
        a1 = ProactiveAlert(
            trend_type=TrendType.INCREASING_ERRORS,
            severity=AlertSeverity.HIGH,
            affected_services=["auth"],
            description="High error rate",
            trend_data=TrendAnalysis(
                metric_name="error_rate",
                current_value=0.3,
                baseline_value=0.05,
                trend_direction="increasing",
                confidence=0.9,
                time_window_minutes=5,
            ),
        )
        a2 = ProactiveAlert(
            trend_type=TrendType.INCREASING_ERRORS,
            severity=AlertSeverity.HIGH,
            affected_services=["auth"],
            description="High error rate",
            trend_data=TrendAnalysis(
                metric_name="error_rate",
                current_value=0.3,
                baseline_value=0.05,
                trend_direction="increasing",
                confidence=0.9,
                time_window_minutes=5,
            ),
        )
        # This was a bug before — mutable default caused same UUID
        assert a1.alert_id != a2.alert_id

    def test_detected_at_is_current(self):
        before = datetime.now()
        alert = ProactiveAlert(
            trend_type=TrendType.MEMORY_LEAK,
            severity=AlertSeverity.CRITICAL,
            affected_services=["cache"],
            description="Memory leak",
            trend_data=TrendAnalysis(
                metric_name="memory",
                current_value=95.0,
                baseline_value=60.0,
                trend_direction="increasing",
                confidence=0.8,
                time_window_minutes=30,
            ),
        )
        assert alert.detected_at >= before


class TestMonitoringResult:
    def test_defaults(self):
        result = MonitoringResult()
        assert result.events_processed == 0
        assert result.trends_detected == []
        assert result.status == "ok"


class TestEnums:
    def test_log_levels(self):
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.FATAL.value == "fatal"

    def test_trend_types(self):
        assert TrendType.MEMORY_LEAK.value == "memory_leak"

    def test_alert_severity_ordering(self):
        severities = [s.value for s in AlertSeverity]
        assert "low" in severities
        assert "critical" in severities
