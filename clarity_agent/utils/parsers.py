"""
Log file parsing utilities for Clarity Agent.

Supports JSON, CSV, and plain text logs.
Normalizes heterogeneous log structures into a unified pandas DataFrame timeline.
"""

import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..utils.logging import logger


# ────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────
def parse_log_files(log_files: List[str]) -> pd.DataFrame:
    """Parse multiple log files and return a consolidated timeline DataFrame."""
    all_events = []

    for log_file in log_files:
        try:
            events = parse_single_log_file(log_file)
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

    logger.info(f"🧩 Consolidated timeline built with {len(df)} total events.")
    return df


# ────────────────────────────────────────────────
# Individual file parsing
# ────────────────────────────────────────────────
def parse_single_log_file(log_file: str) -> List[Dict[str, Any]]:
    """Route parsing to correct handler based on file type."""
    file_path = Path(log_file)
    if not file_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_file}")

    ext = file_path.suffix.lower()
    if ext == ".json":
        return parse_json_log(file_path)
    elif ext == ".csv":
        return parse_csv_log(file_path)
    elif ext in [".log", ".txt"]:
        return parse_text_log(file_path)
    else:
        raise ValueError(f"Unsupported log file format: {ext}")


# ────────────────────────────────────────────────
# JSON
# ────────────────────────────────────────────────
def parse_json_log(file_path: Path) -> List[Dict[str, Any]]:
    """Parse JSON or JSONL log files."""
    events = []

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            events = data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            # JSONL fallback
            f.seek(0)
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON on line {line_num} in {file_path}: {e}")

    normalized = [normalize_event(e, str(file_path)) for e in events if e]
    return [n for n in normalized if n]


# ────────────────────────────────────────────────
# CSV
# ────────────────────────────────────────────────
def parse_csv_log(file_path: Path) -> List[Dict[str, Any]]:
    """Parse CSV log files with headers."""
    events = []
    try:
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            event = row.to_dict()
            norm = normalize_event(event, str(file_path))
            if norm:
                events.append(norm)
    except Exception as e:
        logger.error(f"Failed to parse CSV file {file_path}: {e}")
        raise
    return events


# ────────────────────────────────────────────────
# Plain text
# ────────────────────────────────────────────────
def parse_text_log(file_path: Path) -> List[Dict[str, Any]]:
    """Parse .log or .txt files into structured events."""
    import re

    events = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            event: Dict[str, Any] = {
                "message": line,
                "line_number": line_num,
                "source_file": str(file_path),
            }

            # Extract timestamp & log level
            ts = extract_timestamp_from_text(line)
            if ts:
                event["timestamp"] = ts

            lvl = extract_log_level_from_text(line)
            if lvl:
                event["level"] = lvl

            norm = normalize_event(event, str(file_path))
            if norm:
                events.append(norm)

    return events


# ────────────────────────────────────────────────
# Normalization helpers
# ────────────────────────────────────────────────
def normalize_event(event: Dict[str, Any], source_file: str) -> Dict[str, Any]:
    """Normalize heterogeneous log structures into a consistent format."""
    normalized = {
        "timestamp": datetime.now(),
        "level": "INFO",
        "service": "unknown",
        "message": "",
        "source_file": source_file,
        "metadata": {},
    }

    # Timestamp
    for f in ["timestamp", "time", "@timestamp", "datetime", "date"]:
        if f in event:
            ts = parse_timestamp(event[f])
            if ts:
                normalized["timestamp"] = ts
                break

    # Level
    for f in ["level", "severity", "log_level", "priority"]:
        if f in event:
            normalized["level"] = str(event[f]).upper()
            break

    # Service / Component
    for f in ["service", "component", "module", "app", "application"]:
        if f in event:
            normalized["service"] = str(event[f])
            break

    # Message
    for f in ["message", "msg", "text", "description", "error"]:
        if f in event:
            normalized["message"] = str(event[f])
            break

    if not normalized["message"]:
        normalized["message"] = str(event)

    # Extra fields → metadata
    for k, v in event.items():
        if k not in ["timestamp", "level", "service", "message"]:
            normalized["metadata"][k] = v

    return normalized


# ────────────────────────────────────────────────
# Timestamp & pattern helpers
# ────────────────────────────────────────────────
def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse timestamp strings, numbers, or datetime objects."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


def extract_timestamp_from_text(text: str) -> Optional[datetime]:
    """Regex-based extraction of timestamps from log text lines."""
    import re

    patterns = [
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
        r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})",
        r"(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            ts = parse_timestamp(m.group(1))
            if ts:
                return ts
    return None


def extract_log_level_from_text(text: str) -> Optional[str]:
    """Extract log level keywords like ERROR, WARN, INFO."""
    import re

    levels = ["FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"]
    for lvl in levels:
        if re.search(rf"\b{lvl}\b", text, re.IGNORECASE):
            return lvl
    return None
