"""
Multi-format log parser for Clarity.

Supports JSON, JSONL, CSV, and plain text logs.
Normalizes heterogeneous log structures into a unified pandas DataFrame timeline.
"""

import json
import re
import psutil
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..core import logger


# ────────────────────────────────────────────
# PII Redaction
# ────────────────────────────────────────────

_PII_PATTERNS = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    # Phone numbers (various formats)
    (re.compile(r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"), "[PHONE]"),
    # Credit card numbers (13-16 digits, optionally separated by spaces/dashes)
    (re.compile(r"\b(?:\d[ \-]?){13,16}\b"), "[CARD]"),
    # API key / secret / token / password as key=value or key: value
    (re.compile(
        r"(?i)\b(?:api[_\-]?key|secret|token|password)\s*[=:]\s*\S+",
    ), "[REDACTED]"),
    # Bearer tokens in Authorization headers
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "[REDACTED]"),
]


def _redact_pii(text: str) -> str:
    """Replace PII patterns in *text* with safe placeholder tokens."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────

def parse_log_files(log_files: List[str]) -> pd.DataFrame:
    """Parse multiple log files and return a consolidated timeline DataFrame."""
    all_events: List[Dict[str, Any]] = []

    for log_file in log_files:
        try:
            events = parse_single_file(log_file)
            all_events.extend(events)
            logger.info(f"✅ Parsed {len(events)} events from {log_file}")
        except Exception as e:
            logger.error(f"❌ Failed to parse {log_file}: {e}")
            continue

    if not all_events:
        logger.warning("⚠️ No valid log events parsed from any files.")
        return pd.DataFrame()

    df = pd.DataFrame(all_events)
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info(f"🧩 Consolidated timeline: {len(df)} total events.")
    return df


def parse_single_file(log_file: str) -> List[Dict[str, Any]]:
    """Route parsing to correct handler based on file extension."""
    path = Path(log_file)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {log_file}")

    ext = path.suffix.lower()
    if ext in (".json", ".jsonl"):
        return _parse_json(path)
    elif ext == ".csv":
        return _parse_csv(path)
    elif ext in (".log", ".txt"):
        return _parse_text(path)
    elif ext == ".syslog":
        return _parse_text(path)
    else:
        raise ValueError(f"Unsupported log format: {ext}")


# ────────────────────────────────────────────
# JSON
# ────────────────────────────────────────────

def _parse_json(path: Path) -> List[Dict[str, Any]]:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            raw = data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            # JSONL fallback
            f.seek(0)
            raw = []
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON on line {i} in {path}: {e}")

    for item in raw:
        norm = _normalize_event(item, str(path))
        if norm:
            events.append(norm)
    return events


# ────────────────────────────────────────────
# CSV
# ────────────────────────────────────────────

def _parse_csv(path: Path) -> List[Dict[str, Any]]:
    events = []
    if psutil.virtual_memory().percent > 80:
        logger.warning(f"Memory usage >80%, streaming {path} in chunks")
        for chunk in pd.read_csv(path, chunksize=10_000):
            for _, row in chunk.iterrows():
                norm = _normalize_event(row.to_dict(), str(path))
                if norm:
                    events.append(norm)
    else:
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            norm = _normalize_event(row.to_dict(), str(path))
            if norm:
                events.append(norm)
    return events


# ────────────────────────────────────────────
# Plain text
# ────────────────────────────────────────────

def _parse_text(path: Path) -> List[Dict[str, Any]]:
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            event: Dict[str, Any] = {
                "message": line,
                "line_number": line_num,
                "source_file": str(path),
            }

            ts = _extract_timestamp(line)
            if ts:
                event["timestamp"] = ts

            lvl = _extract_log_level(line)
            if lvl:
                event["level"] = lvl

            norm = _normalize_event(event, str(path))
            if norm:
                events.append(norm)
    return events


# ────────────────────────────────────────────
# Normalization
# ────────────────────────────────────────────

_TIMESTAMP_KEYS = ["timestamp", "time", "@timestamp", "datetime", "date"]
_LEVEL_KEYS = ["level", "severity", "log_level", "priority"]
_SERVICE_KEYS = ["service", "component", "module", "app", "application"]
_MESSAGE_KEYS = ["message", "msg", "text", "description", "error"]


def _normalize_event(event: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    """Normalize heterogeneous log structures into a consistent format."""
    normalized: Dict[str, Any] = {
        "timestamp": datetime.now(),
        "level": "INFO",
        "service": "unknown",
        "message": "",
        "source_file": source_file,
        "metadata": {},
    }

    # Timestamp
    for key in _TIMESTAMP_KEYS:
        if key in event:
            ts = _parse_timestamp(event[key])
            if ts:
                normalized["timestamp"] = ts
                break

    # Level
    for key in _LEVEL_KEYS:
        if key in event:
            normalized["level"] = str(event[key]).upper()
            break

    # Service
    for key in _SERVICE_KEYS:
        if key in event:
            normalized["service"] = str(event[key])
            break

    # Message
    for key in _MESSAGE_KEYS:
        if key in event:
            normalized["message"] = str(event[key])
            break

    if not normalized["message"]:
        normalized["message"] = str(event)

    # Redact PII from the message field
    normalized["message"] = _redact_pii(normalized["message"])

    # Remaining fields → metadata
    known_keys = set(_TIMESTAMP_KEYS + _LEVEL_KEYS + _SERVICE_KEYS + _MESSAGE_KEYS)
    for k, v in event.items():
        if k not in known_keys:
            normalized["metadata"][k] = v

    return normalized


# ────────────────────────────────────────────
# Timestamp parsing
# ────────────────────────────────────────────

_TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%d/%m/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d",
]

_TIMESTAMP_PATTERNS = [
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
    r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
    r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",
]

_LOG_LEVELS = ["FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"]


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        for fmt in _TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def _extract_timestamp(text: str) -> Optional[datetime]:
    for pattern in _TIMESTAMP_PATTERNS:
        m = re.search(pattern, text)
        if m:
            ts = _parse_timestamp(m.group(1))
            if ts:
                return ts
    return None


def _extract_log_level(text: str) -> Optional[str]:
    for lvl in _LOG_LEVELS:
        if re.search(rf"\b{lvl}\b", text, re.IGNORECASE):
            return lvl
    return None
