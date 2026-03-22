"""Tests for Clarity log parser module."""

import json
import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime

from clarity.parsers.log_parser import (
    parse_log_files,
    parse_single_file,
    _parse_timestamp,
    _extract_timestamp,
    _extract_log_level,
    _normalize_event,
)


# ─── Multi-file Parsing ─────────────────────────


class TestParseLogFiles:
    """Tests for the top-level parse_log_files function."""

    def test_parses_multiple_files(self, sample_json_log, sample_csv_log):
        df = parse_log_files([sample_json_log, sample_csv_log])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 8  # 4 JSON + 4 CSV
        assert "timestamp" in df.columns
        assert "level" in df.columns

    def test_returns_empty_for_no_valid_files(self, tmp_dir):
        df = parse_log_files([str(tmp_dir / "nonexistent.log")])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_returns_empty_for_empty_file(self, empty_log):
        df = parse_log_files([empty_log])
        assert df.empty

    def test_continues_on_bad_file(self, sample_json_log, tmp_dir):
        bad = str(tmp_dir / "nope.log")
        df = parse_log_files([bad, sample_json_log])
        assert len(df) == 4  # Only JSON file parsed

    def test_sorts_by_timestamp(self, sample_json_log):
        df = parse_log_files([sample_json_log])
        timestamps = df["timestamp"].tolist()
        assert timestamps == sorted(timestamps)

    def test_empty_list_returns_empty_df(self):
        df = parse_log_files([])
        assert df.empty


# ─── Single File Parsing ────────────────────────


class TestParseSingleFile:
    """Tests for individual file format parsing."""

    def test_parse_json(self, sample_json_log):
        events = parse_single_file(sample_json_log)
        assert len(events) == 4
        assert events[0]["level"] == "ERROR"
        assert events[0]["service"] == "auth-service"

    def test_parse_jsonl(self, sample_jsonl_log):
        events = parse_single_file(sample_jsonl_log)
        assert len(events) == 3  # empty line skipped

    def test_parse_csv(self, sample_csv_log):
        events = parse_single_file(sample_csv_log)
        assert len(events) == 4
        assert events[0]["level"] == "ERROR"

    def test_parse_text_log(self, sample_text_log):
        events = parse_single_file(sample_text_log)
        assert len(events) == 5
        # Check that levels are extracted
        levels = [e["level"] for e in events]
        assert "ERROR" in levels
        assert "FATAL" in levels

    def test_parse_malformed_json(self, malformed_json_log):
        """Should recover what it can from malformed JSON."""
        events = parse_single_file(malformed_json_log)
        # Should get at least the valid JSONL line
        assert len(events) >= 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_single_file("/nonexistent/path.log")

    def test_unsupported_format(self, tmp_dir):
        path = tmp_dir / "data.xml"
        path.write_text("<log></log>")
        with pytest.raises(ValueError, match="Unsupported"):
            parse_single_file(str(path))


# ─── Timestamp Parsing ──────────────────────────


class TestTimestampParsing:
    """Tests for timestamp extraction and parsing."""

    @pytest.mark.parametrize("value,expected_year", [
        ("2024-01-15 10:30:00", 2024),
        ("2024-01-15T10:30:00", 2024),
        ("2024-01-15T10:30:00Z", 2024),
        ("2024-01-15T10:30:00.123456", 2024),
        ("2024-01-15T10:30:00.123456Z", 2024),
        ("15/01/2024 10:30:00", 2024),
        ("2024-01-15", 2024),
    ])
    def test_parse_string_timestamps(self, value, expected_year):
        result = _parse_timestamp(value)
        assert result is not None
        assert result.year == expected_year

    def test_parse_datetime_passthrough(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert _parse_timestamp(dt) == dt

    def test_parse_unix_timestamp(self):
        result = _parse_timestamp(1705312200.0)
        assert result is not None
        assert result.year == 2024

    def test_parse_invalid_returns_none(self):
        assert _parse_timestamp("not a date") is None
        assert _parse_timestamp("") is None

    def test_extract_timestamp_from_text(self):
        result = _extract_timestamp("2024-01-15 10:30:00 ERROR something failed")
        assert result is not None
        assert result.year == 2024

    def test_extract_timestamp_iso(self):
        result = _extract_timestamp("[2024-01-15T10:30:00] ERROR: boom")
        assert result is not None

    def test_no_timestamp_returns_none(self):
        assert _extract_timestamp("just some error text") is None


# ─── Log Level Extraction ───────────────────────


class TestLogLevelExtraction:
    """Tests for log level detection in text."""

    @pytest.mark.parametrize("text,expected", [
        ("2024-01-15 ERROR something", "ERROR"),
        ("WARN: approaching limit", "WARN"),
        ("This is an INFO message", "INFO"),
        ("FATAL crash detected", "FATAL"),
        ("DEBUG mode enabled", "DEBUG"),
    ])
    def test_extracts_level(self, text, expected):
        assert _extract_log_level(text) == expected

    def test_case_insensitive(self):
        assert _extract_log_level("error: something broke") == "ERROR"

    def test_no_level_returns_none(self):
        assert _extract_log_level("just some normal text") is None

    def test_word_boundary(self):
        """Should not match 'ERROR' inside another word."""
        result = _extract_log_level("TERROR in the logs")
        # This should NOT match since TERROR contains ERROR but isn't the word ERROR
        # However regex \bERROR\b would not match in TERROR, so this should be None
        # Actually \bERROR\b matches ERROR as a whole word, TERROR contains ERROR but
        # with T before it, so \b won't match there
        # But FATAL, ERROR etc are checked in order, let's see
        assert result is None  # "TERROR" should not trigger "ERROR"


# ─── Event Normalization ────────────────────────


class TestNormalization:
    """Tests for event normalization."""

    def test_normalizes_standard_event(self):
        event = {
            "timestamp": "2024-01-15T10:30:00",
            "level": "error",
            "service": "auth-service",
            "message": "Connection failed",
        }
        result = _normalize_event(event, "test.log")
        assert result["level"] == "ERROR"
        assert result["service"] == "auth-service"
        assert result["source_file"] == "test.log"

    def test_handles_alternative_field_names(self):
        event = {
            "@timestamp": "2024-01-15T10:30:00",
            "severity": "WARN",
            "component": "api-gateway",
            "msg": "Timeout detected",
        }
        result = _normalize_event(event, "test.log")
        assert result["level"] == "WARN"
        assert result["service"] == "api-gateway"
        assert result["message"] == "Timeout detected"

    def test_preserves_extra_fields_as_metadata(self):
        event = {
            "level": "ERROR",
            "message": "Crash",
            "request_id": "abc-123",
            "user_agent": "curl/7.0",
        }
        result = _normalize_event(event, "test.log")
        assert "request_id" in result["metadata"]
        assert result["metadata"]["request_id"] == "abc-123"

    def test_fallback_message(self):
        event = {"some_random_field": "value"}
        result = _normalize_event(event, "test.log")
        assert result["message"]  # Should have something, not empty


# ─── Integration with Real Log Files ────────────


class TestRealLogFiles:
    """Integration tests using the actual sample log files shipped with Clarity."""

    @pytest.fixture
    def logs_dir(self) -> Path:
        return Path("e:/Clarity/logs")

    def test_parse_app_errors(self, logs_dir):
        path = logs_dir / "app_errors.log"
        if path.exists():
            events = parse_single_file(str(path))
            assert len(events) > 0
            assert all("message" in e for e in events)

    def test_parse_deployment_logs(self, logs_dir):
        path = logs_dir / "deployment_logs.json"
        if path.exists():
            events = parse_single_file(str(path))
            assert len(events) > 0

    def test_parse_config_changes(self, logs_dir):
        path = logs_dir / "config_changes.csv"
        if path.exists():
            events = parse_single_file(str(path))
            assert len(events) > 0

    def test_full_pipeline(self, logs_dir):
        """Parse all available log files together."""
        files = [str(f) for f in logs_dir.glob("*") if f.suffix in (".log", ".json", ".csv")]
        if files:
            df = parse_log_files(files)
            assert not df.empty
            assert "timestamp" in df.columns
