"""Pydantic data models for Clarity."""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator
import uuid


# ─── Enums ───────────────────────────────────────


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class TrendType(str, Enum):
    INCREASING_ERRORS = "increasing_errors"
    RISING_LATENCY = "rising_latency"
    MEMORY_LEAK = "memory_leak"
    DISK_USAGE_GROWTH = "disk_usage_growth"
    CONNECTION_POOL_EXHAUSTION = "connection_pool_exhaustion"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Core Models ─────────────────────────────────


class LogEvent(BaseModel):
    """Normalized log entry."""
    timestamp: datetime
    level: str = "INFO"
    service: str = "unknown"
    message: str
    source_file: str = ""
    metadata: Dict[str, Any] = {}


class RootCause(BaseModel):
    """Root cause analysis result."""
    summary: str
    description: str
    affected_components: List[str]
    confidence_score: float

    @field_validator("confidence_score")
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v


class RemediationCommand(BaseModel):
    """A remediation action."""
    command: str
    strategy: str = "manual"
    description: str = ""
    risk_level: str = "LOW"
    requires_approval: bool = True


class AnalysisResult(BaseModel):
    """Complete incident analysis output."""
    incident_id: str = Field(default_factory=lambda: f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}")
    timeline: List[LogEvent] = []
    root_cause: Optional[RootCause] = None
    remediation: Optional[RemediationCommand] = None
    events_processed: int = 0
    processing_time_ms: int = 0
    ai_model: str = ""


# ─── Monitoring Models ───────────────────────────


class TrendAnalysis(BaseModel):
    """Detected trend in system metrics."""
    metric_name: str
    current_value: float
    baseline_value: float
    trend_direction: str
    confidence: float
    time_window_minutes: int
    data_points: List[Dict[str, Any]] = []


class ProactiveAlert(BaseModel):
    """Alert from proactive monitoring."""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: datetime = Field(default_factory=datetime.now)
    trend_type: TrendType
    severity: AlertSeverity
    affected_services: List[str]
    description: str
    trend_data: TrendAnalysis
    recommended_actions: List[str] = []
    resolved_at: Optional[datetime] = None


class MonitoringResult(BaseModel):
    """Result of a monitoring scan cycle."""
    scan_time: datetime = Field(default_factory=datetime.now)
    events_processed: int = 0
    trends_detected: List[ProactiveAlert] = []
    status: str = "ok"
    scan_number: int = 0
