"""Shared test fixtures for Clarity tests."""

import json
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_json_log(tmp_dir: Path) -> str:
    """Create a sample JSON log file."""
    data = [
        {
            "timestamp": "2024-01-15T10:30:00",
            "level": "ERROR",
            "service": "auth-service",
            "message": "Database connection pool exhausted",
        },
        {
            "timestamp": "2024-01-15T10:30:05",
            "level": "WARN",
            "service": "auth-service",
            "message": "Retrying database connection",
        },
        {
            "timestamp": "2024-01-15T10:30:10",
            "level": "INFO",
            "service": "api-gateway",
            "message": "Health check passed",
        },
        {
            "timestamp": "2024-01-15T10:30:15",
            "level": "ERROR",
            "service": "auth-service",
            "message": "Connection timeout after 30s",
        },
    ]
    path = tmp_dir / "app.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_jsonl_log(tmp_dir: Path) -> str:
    """Create a sample JSONL log file."""
    lines = [
        '{"timestamp": "2024-01-15T10:30:00", "level": "ERROR", "service": "payment-service", "message": "Payment gateway timeout"}',
        '{"timestamp": "2024-01-15T10:30:01", "level": "INFO", "service": "payment-service", "message": "Retrying payment"}',
        '',  # empty line (should be skipped)
        '{"timestamp": "2024-01-15T10:30:02", "level": "ERROR", "service": "payment-service", "message": "Payment failed permanently"}',
    ]
    path = tmp_dir / "payments.json"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_csv_log(tmp_dir: Path) -> str:
    """Create a sample CSV log file."""
    csv_content = """timestamp,level,service,message
2024-01-15 10:30:00,ERROR,database,Disk usage at 95%
2024-01-15 10:30:05,WARN,database,Slow query detected: 5200ms
2024-01-15 10:30:10,ERROR,database,Max connections reached
2024-01-15 10:30:15,INFO,database,Connection pool expanded"""
    path = tmp_dir / "db.csv"
    path.write_text(csv_content, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_text_log(tmp_dir: Path) -> str:
    """Create a sample plain text log file."""
    content = """2024-01-15 10:30:00 ERROR [auth-service] Failed to authenticate user: token expired
2024-01-15 10:30:01 INFO [auth-service] Refreshing auth token
2024-01-15 10:30:02 WARN [auth-service] Rate limit approaching: 450/500 requests
2024-01-15 10:30:03 ERROR [api-gateway] Upstream service unavailable: auth-service
2024-01-15 10:30:04 FATAL [auth-service] Service crashed: OutOfMemoryError"""
    path = tmp_dir / "app.log"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture
def empty_log(tmp_dir: Path) -> str:
    """Create an empty log file."""
    path = tmp_dir / "empty.log"
    path.write_text("", encoding="utf-8")
    return str(path)


@pytest.fixture
def malformed_json_log(tmp_dir: Path) -> str:
    """Create a malformed JSON log file."""
    content = '{"timestamp": "2024-01-15", "broken": true\n{"valid": true, "level": "ERROR", "message": "test"}\nnot json at all'
    path = tmp_dir / "broken.json"
    path.write_text(content, encoding="utf-8")
    return str(path)
