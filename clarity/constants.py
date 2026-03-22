"""Application-wide constants for Clarity."""

# Supported log file formats
SUPPORTED_LOG_FORMATS = [
    "json",     # Structured JSON logs
    "jsonl",    # JSON Lines format
    "csv",      # CSV formatted logs
    "log",      # Plain text logs
    "txt",      # Generic text files
    "syslog",   # Syslog format
]

# Known service names for remediation routing
KNOWN_SERVICES = [
    "auth-service",
    "api-service",
    "user-service",
    "payment-service",
    "database",
    "api-gateway",
    "cache-service",
]

# Remediation strategy mapping
REMEDIATION_STRATEGIES = {
    "memory_leak": ["restart", "increase_memory", "rollback"],
    "database_connection": ["scale_pool", "restart_db", "check_config"],
    "rate_limit": ["increase_limit", "add_caching", "load_balance"],
    "disk_space": ["cleanup", "increase_volume", "archive_logs"],
    "deployment_bug": ["rollback", "hotfix", "feature_flag"],
    "resource_exhaustion": ["restart", "scale", "increase_limits"],
    "configuration_error": ["rollback", "hotfix", "revert_config"],
}

# Log level priority (higher = more severe)
LOG_LEVEL_PRIORITY = {
    "DEBUG": 0,
    "TRACE": 0,
    "INFO": 1,
    "WARN": 2,
    "WARNING": 2,
    "ERROR": 3,
    "FATAL": 4,
    "CRITICAL": 4,
}

# Terminal color scheme
COLORS = {
    "primary": "blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "cyan",
    "dim": "dim",
    "accent": "magenta",
}
