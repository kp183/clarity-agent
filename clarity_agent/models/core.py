from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, field_validator
import uuid

# --- Enums for standardized values ---
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

# --- AWS-Specific Models ---
class AWSResourceInfo(BaseModel):
    """Represents a tagged AWS resource."""
    arn: str
    resource_type: str
    region: str

class BedrockRequest(BaseModel):
    """Model for a request sent to AWS Bedrock."""
    model_id: str
    prompt: str
    max_tokens: int = 4096

class BedrockResponse(BaseModel):
    """Model for a response received from AWS Bedrock."""
    completion: str
    stop_reason: str
    token_usage: Dict[str, int]

# --- Core Application Models ---
class LogEvent(BaseModel):
    """Represents a single, structured log entry."""
    timestamp: datetime
    level: LogLevel
    service: str
    message: str
    source_file: str
    aws_info: Optional[AWSResourceInfo] = None # AWS-specific field

    @field_validator('timestamp')
    def timestamp_must_be_valid(cls, v):
        # Allow for a small buffer for clock drift
        if v > datetime.now() + timedelta(minutes=5):
            raise ValueError('Timestamp cannot be in the future')
        return v

class RootCause(BaseModel):
    """The identified root cause of an incident."""
    summary: str
    description: str
    affected_components: List[str]
    confidence_score: float

    @field_validator('confidence_score')
    def confidence_must_be_valid(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Confidence score must be between 0.0 and 1.0')
        return v

class Evidence(BaseModel):
    """Supporting evidence for a root cause analysis."""
    description: str
    log_entries: List[LogEvent]

class RemediationCommand(BaseModel):
    """A command to remediate an issue."""
    command: str
    description: str
    requires_approval: bool = True

class AnalysisResult(BaseModel):
    """Complete result of a reactive incident analysis."""
    incident_id: str = str(uuid.uuid4())
    timeline: List[LogEvent]
    root_cause: Optional[RootCause] = None
    evidence: List[Evidence] = []
    remediation_commands: List[RemediationCommand] = []