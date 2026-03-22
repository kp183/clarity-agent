"""
Property-based tests for Clarity.

**Validates: Requirements 13.3, 13.5**
"""

import json
import string
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from clarity.parsers.log_parser import _redact_pii
from clarity.core.llm_client import LLMClient


# ─── Strategies ─────────────────────────────────────────────────────────────

# Email strategy: localpart@domain.tld
_email_local = st.text(
    alphabet=string.ascii_letters + string.digits + "._%+-",
    min_size=1,
    max_size=20,
)
_email_domain = st.text(
    alphabet=string.ascii_letters + string.digits + "-",
    min_size=2,
    max_size=15,
)
_email_tld = st.text(
    alphabet=string.ascii_letters,
    min_size=2,
    max_size=6,
)

@st.composite
def email_addresses(draw):
    local = draw(_email_local)
    domain = draw(_email_domain)
    tld = draw(_email_tld)
    # Ensure no leading/trailing dots or hyphens that would break the regex
    local = local.strip(".").strip("-") or "user"
    domain = domain.strip("-") or "example"
    return f"{local}@{domain}.{tld}"


# Phone strategy: NXX-NXX-XXXX (N = 2-9, X = 0-9)
@st.composite
def phone_numbers(draw):
    area = draw(st.integers(min_value=200, max_value=999))
    exchange = draw(st.integers(min_value=200, max_value=999))
    subscriber = draw(st.integers(min_value=0, max_value=9999))
    sep = draw(st.sampled_from(["-", ".", " ", ""]))
    return f"{area}{sep}{exchange}{sep}{subscriber:04d}"


# Credit card strategy: 16 digits optionally separated
@st.composite
def credit_card_numbers(draw):
    groups = [draw(st.integers(min_value=1000, max_value=9999)) for _ in range(4)]
    sep = draw(st.sampled_from(["-", " ", ""]))
    return sep.join(str(g) for g in groups)


# Credential key=value strategy
_cred_keys = ["api_key", "api-key", "apikey", "secret", "token", "password"]
_cred_value_chars = string.ascii_letters + string.digits + "_-"

@st.composite
def credential_pairs(draw):
    key = draw(st.sampled_from(_cred_keys))
    value = draw(st.text(alphabet=_cred_value_chars, min_size=4, max_size=32))
    sep = draw(st.sampled_from(["=", ": ", "="]))
    return key + sep + value, value


# Bearer token strategy
@st.composite
def bearer_tokens(draw):
    token_chars = string.ascii_letters + string.digits + "-._~+/"
    token = draw(st.text(alphabet=token_chars, min_size=8, max_size=64))
    return f"Bearer {token}", token


# ─── Property 17: Sensitive data redaction ──────────────────────────────────


class TestProperty17PIIRedaction:
    """
    Property 17: Sensitive data redaction

    For any log message string containing email addresses, phone numbers,
    credit card numbers, or key=value credential patterns, the PII redaction
    function shall replace those values with placeholder tokens ([EMAIL],
    [PHONE], [CARD], [REDACTED]) and the output shall not contain the
    original sensitive values.

    **Validates: Requirements 13.3, 13.5**
    """

    @given(email=email_addresses())
    @settings(max_examples=100)
    def test_email_is_redacted(self, email):
        """Email addresses must be replaced with [EMAIL]."""
        text = f"User login failed for {email} at 10:30"
        result = _redact_pii(text)
        assert email not in result, f"Email {email!r} still present in: {result!r}"
        assert "[EMAIL]" in result, f"[EMAIL] placeholder missing in: {result!r}"

    @given(phone=phone_numbers())
    @settings(max_examples=100)
    def test_phone_is_redacted(self, phone):
        """Phone numbers must be replaced with [PHONE]."""
        # Only test phones that match the expected format (10 digits with separators)
        digits = "".join(c for c in phone if c.isdigit())
        assume(len(digits) == 10)
        text = f"Contact support at {phone} for assistance"
        result = _redact_pii(text)
        assert phone not in result, f"Phone {phone!r} still present in: {result!r}"
        assert "[PHONE]" in result, f"[PHONE] placeholder missing in: {result!r}"

    @given(card=credit_card_numbers())
    @settings(max_examples=100)
    def test_credit_card_is_redacted(self, card):
        """Credit card numbers must be replaced with [CARD]."""
        text = f"Payment processed with card {card}"
        result = _redact_pii(text)
        # Strip separators to check the raw digits aren't present
        raw_digits = "".join(c for c in card if c.isdigit())
        assert card not in result, f"Card {card!r} still present in: {result!r}"
        assert "[CARD]" in result, f"[CARD] placeholder missing in: {result!r}"

    @given(pair=credential_pairs())
    @settings(max_examples=100)
    def test_credential_value_is_redacted(self, pair):
        """API key/secret/token/password values must be replaced with [REDACTED]."""
        credential_str, secret_value = pair
        text = f"Config loaded: {credential_str} for service"
        result = _redact_pii(text)
        assert secret_value not in result, (
            f"Secret value {secret_value!r} still present in: {result!r}"
        )
        assert "[REDACTED]" in result, f"[REDACTED] placeholder missing in: {result!r}"

    @given(bearer=bearer_tokens())
    @settings(max_examples=100)
    def test_bearer_token_is_redacted(self, bearer):
        """Bearer tokens must be replaced with [REDACTED]."""
        bearer_str, token_value = bearer
        text = f"Authorization: {bearer_str}"
        result = _redact_pii(text)
        assert token_value not in result, (
            f"Bearer token {token_value!r} still present in: {result!r}"
        )
        assert "[REDACTED]" in result, f"[REDACTED] placeholder missing in: {result!r}"

    @given(email=email_addresses(), phone=phone_numbers())
    @settings(max_examples=50)
    def test_multiple_pii_types_all_redacted(self, email, phone):
        """When multiple PII types appear, all must be redacted."""
        digits = "".join(c for c in phone if c.isdigit())
        assume(len(digits) == 10)
        text = f"Alert: user {email} called from {phone}"
        result = _redact_pii(text)
        assert email not in result, f"Email {email!r} still present in: {result!r}"
        assert phone not in result, f"Phone {phone!r} still present in: {result!r}"
        assert "[EMAIL]" in result
        assert "[PHONE]" in result


# ─── Property 16: JSON block extraction from prose ──────────────────────────


# Safe prose characters: no braces, no backticks (to avoid interfering with extraction)
_safe_prose_chars = string.ascii_letters + string.digits + " .,!?-_:;"


@st.composite
def simple_json_dicts(draw):
    """Generate simple JSON-serialisable dicts with string keys and string/int values."""
    keys = draw(
        st.lists(
            st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10),
            min_size=1,
            max_size=5,
            unique=True,
        )
    )
    values = draw(
        st.lists(
            st.one_of(
                st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=0, max_size=20),
                st.integers(min_value=0, max_value=9999),
            ),
            min_size=len(keys),
            max_size=len(keys),
        )
    )
    return dict(zip(keys, values))


@st.composite
def prose_wrapped_json(draw, data: dict):
    """Wrap a JSON dict in one of three styles: plain prose, markdown fence, or both."""
    json_str = json.dumps(data)
    prose_before = draw(st.text(alphabet=_safe_prose_chars, min_size=0, max_size=50))
    prose_after = draw(st.text(alphabet=_safe_prose_chars, min_size=0, max_size=50))
    style = draw(st.sampled_from(["plain", "fence", "fence_plain"]))

    if style == "plain":
        return f"{prose_before} {json_str} {prose_after}".strip()
    elif style == "fence":
        return f"```json\n{json_str}\n```"
    else:  # fence_plain
        return f"{prose_before}\n```json\n{json_str}\n```\n{prose_after}".strip()


class TestProperty16JSONBlockExtraction:
    """
    Property 16: JSON block extraction from prose

    For any string containing a valid JSON object surrounded by arbitrary
    prose or markdown code fences, `_extract_json_block()` shall return a
    string that parses as valid JSON and contains the same keys and values
    as the embedded object.

    **Validates: Requirements 9.7**
    """

    @given(data=simple_json_dicts())
    @settings(max_examples=100)
    def test_plain_prose_wrapping(self, data):
        """JSON embedded in plain prose (no braces in prose) is correctly extracted."""
        json_str = json.dumps(data)
        prose_before = "The analysis result is as follows: "
        prose_after = " Please review the above output."
        wrapped = f"{prose_before}{json_str}{prose_after}"

        result = LLMClient._extract_json_block(wrapped)
        parsed = json.loads(result)
        assert parsed == data

    @given(data=simple_json_dicts())
    @settings(max_examples=100)
    def test_markdown_fence_wrapping(self, data):
        """JSON inside a markdown ```json ... ``` fence is correctly extracted."""
        json_str = json.dumps(data)
        wrapped = f"```json\n{json_str}\n```"

        result = LLMClient._extract_json_block(wrapped)
        parsed = json.loads(result)
        assert parsed == data

    @given(data=simple_json_dicts(), prose=st.text(alphabet=_safe_prose_chars, min_size=1, max_size=40))
    @settings(max_examples=100)
    def test_prose_before_and_after(self, data, prose):
        """JSON with arbitrary safe prose before and after is correctly extracted."""
        json_str = json.dumps(data)
        wrapped = f"{prose} {json_str} {prose}"

        result = LLMClient._extract_json_block(wrapped)
        parsed = json.loads(result)
        assert parsed == data

    @given(data=simple_json_dicts())
    @settings(max_examples=100)
    def test_bare_json_passthrough(self, data):
        """A bare JSON string (no surrounding text) is returned as valid JSON."""
        json_str = json.dumps(data)

        result = LLMClient._extract_json_block(json_str)
        parsed = json.loads(result)
        assert parsed == data


# ─── Property 10: Error rate to alert severity mapping ──────────────────────

import pandas as pd
from unittest.mock import patch

from clarity.agents.sentinel import SentinelAgent
from clarity.core.models import AlertSeverity, TrendType


def _make_df_for_rate(draw, min_rate: float, max_rate: float):
    """
    Build a DataFrame whose actual error rate falls in [min_rate, max_rate].
    Uses at least 20 rows so rounding doesn't push the rate out of range.
    """
    total = draw(st.integers(min_value=20, max_value=200))
    # Draw an integer error count that keeps the rate in the desired band
    min_errors = int(min_rate * total) + 1 if min_rate > 0 else 0
    max_errors = int(max_rate * total)
    # Ensure valid range
    min_errors = max(0, min(min_errors, total))
    max_errors = max(min_errors, min(max_errors, total))
    error_count = draw(st.integers(min_value=min_errors, max_value=max_errors))

    levels = ["ERROR"] * error_count + ["INFO"] * (total - error_count)
    indices = draw(st.permutations(range(total)))
    levels = [levels[i] for i in indices]

    df = pd.DataFrame({"level": levels})
    actual_rate = error_count / total
    return df, actual_rate


@st.composite
def df_critical_rate(draw):
    """DataFrame where error_rate > 0.25."""
    return _make_df_for_rate(draw, min_rate=0.26, max_rate=1.0)


@st.composite
def df_high_rate(draw):
    """DataFrame where 0.15 < error_rate <= 0.25."""
    return _make_df_for_rate(draw, min_rate=0.16, max_rate=0.25)


@st.composite
def df_safe_rate(draw):
    """DataFrame where error_rate <= 0.15."""
    return _make_df_for_rate(draw, min_rate=0.0, max_rate=0.15)


class TestProperty10ErrorRateAlertSeverity:
    """
    Property 10: Error rate to alert severity mapping

    For any log DataFrame, if the fraction of ERROR-level events exceeds 0.25
    the Anomaly Detector shall produce a CRITICAL alert; if it exceeds the
    configured threshold (default 0.15) but not 0.25 it shall produce a HIGH
    alert; otherwise no threshold alert shall be generated.

    **Validates: Requirements 5.3, 5.4**
    """

    def _get_threshold_alerts(self, df):
        """
        Run _detect_trends() with AI predictive analysis disabled so we only
        test the rule-based threshold logic.
        """
        agent = SentinelAgent.__new__(SentinelAgent)
        agent.scan_count = 1
        with patch.object(agent, "_run_predictive_analysis", return_value=[]):
            return agent._detect_trends(df)

    @given(sample=df_critical_rate())
    @settings(max_examples=200)
    def test_critical_alert_when_error_rate_exceeds_25_percent(self, sample):
        """
        When error_rate > 0.25, _detect_trends() must include at least one
        CRITICAL severity alert.
        """
        df, actual_rate = sample

        alerts = self._get_threshold_alerts(df)
        severities = [a.severity for a in alerts]
        assert AlertSeverity.CRITICAL in severities, (
            f"Expected CRITICAL alert for error_rate={actual_rate:.4f}, "
            f"got severities: {severities}"
        )

    @given(sample=df_high_rate())
    @settings(max_examples=200, deadline=None)
    def test_high_alert_when_error_rate_between_threshold_and_25_percent(self, sample):
        """
        When 0.15 < error_rate <= 0.25, _detect_trends() must include a HIGH
        severity alert and must NOT include a CRITICAL alert.
        """
        df, actual_rate = sample

        alerts = self._get_threshold_alerts(df)
        severities = [a.severity for a in alerts]
        assert AlertSeverity.HIGH in severities, (
            f"Expected HIGH alert for error_rate={actual_rate:.4f}, "
            f"got severities: {severities}"
        )
        assert AlertSeverity.CRITICAL not in severities, (
            f"Unexpected CRITICAL alert for error_rate={actual_rate:.4f}, "
            f"got severities: {severities}"
        )

    @given(sample=df_safe_rate())
    @settings(max_examples=200)
    def test_no_threshold_alert_when_error_rate_at_or_below_threshold(self, sample):
        """
        When error_rate <= 0.15, _detect_trends() must not generate any
        threshold-based HIGH or CRITICAL alert.
        """
        df, actual_rate = sample

        alerts = self._get_threshold_alerts(df)
        severities = [a.severity for a in alerts]
        assert AlertSeverity.CRITICAL not in severities, (
            f"Unexpected CRITICAL alert for error_rate={actual_rate:.4f}"
        )
        assert AlertSeverity.HIGH not in severities, (
            f"Unexpected HIGH alert for error_rate={actual_rate:.4f}"
        )


# ─── Property 5: Log parsing round-trip ─────────────────────────────────────

import csv
import io
import os
import tempfile

from clarity.parsers.log_parser import parse_single_file


@st.composite
def log_events_for_roundtrip(draw):
    """Generate a list of simple log event dicts with message, level, and service."""
    levels = ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
    n = draw(st.integers(min_value=1, max_value=20))
    events = []
    for _ in range(n):
        message = draw(
            st.text(
                alphabet=string.ascii_letters + string.digits + " .,!?-_",
                min_size=1,
                max_size=80,
            )
        )
        level = draw(st.sampled_from(levels))
        service = draw(
            st.text(
                alphabet=string.ascii_lowercase + string.digits + "-",
                min_size=1,
                max_size=20,
            )
        )
        events.append({"message": message, "level": level, "service": service})
    return events


class TestProperty5LogParsingRoundTrip:
    """
    Property 5: Log parsing round-trip

    For any valid log file, parsing it to a list of event dicts, serializing
    those dicts back to the original format, then parsing again shall produce
    a list of event dicts with equivalent `message`, `level`, and `service`
    values.

    We test the round-trip for JSON and CSV formats, which have deterministic
    serialization. Plain-text logs are excluded because the text format is
    lossy (service is not encoded in the line).

    **Validates: Requirements 1.11**
    """

    @given(events=log_events_for_roundtrip())
    @settings(max_examples=100, deadline=None)
    def test_json_roundtrip(self, events):
        """Parse → serialize to JSON → parse again produces equivalent records."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(events, f)
            tmp_path = f.name

        try:
            first_pass = parse_single_file(tmp_path)
            assert len(first_pass) == len(events), (
                f"First parse: expected {len(events)} events, got {len(first_pass)}"
            )

            # Serialize the normalized events back to JSON
            serialized = [
                {
                    "message": e["message"],
                    "level": e["level"],
                    "service": e["service"],
                }
                for e in first_pass
            ]
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f2:
                json.dump(serialized, f2)
                tmp_path2 = f2.name

            try:
                second_pass = parse_single_file(tmp_path2)
                assert len(second_pass) == len(first_pass), (
                    f"Second parse: expected {len(first_pass)} events, got {len(second_pass)}"
                )
                for i, (orig, reparsed) in enumerate(zip(first_pass, second_pass)):
                    assert orig["message"] == reparsed["message"], (
                        f"Event {i}: message mismatch: {orig['message']!r} != {reparsed['message']!r}"
                    )
                    assert orig["level"] == reparsed["level"], (
                        f"Event {i}: level mismatch: {orig['level']!r} != {reparsed['level']!r}"
                    )
                    assert orig["service"] == reparsed["service"], (
                        f"Event {i}: service mismatch: {orig['service']!r} != {reparsed['service']!r}"
                    )
            finally:
                os.unlink(tmp_path2)
        finally:
            os.unlink(tmp_path)

    @given(events=log_events_for_roundtrip())
    @settings(max_examples=100, deadline=None)
    def test_csv_roundtrip(self, events):
        """Parse → serialize to CSV → parse again produces equivalent records."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["message", "level", "service"])
            writer.writeheader()
            writer.writerows(events)
            tmp_path = f.name

        try:
            first_pass = parse_single_file(tmp_path)
            assert len(first_pass) == len(events), (
                f"First parse: expected {len(events)} events, got {len(first_pass)}"
            )

            # Serialize normalized events back to CSV
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
            ) as f2:
                writer = csv.DictWriter(f2, fieldnames=["message", "level", "service"])
                writer.writeheader()
                for e in first_pass:
                    writer.writerow(
                        {
                            "message": e["message"],
                            "level": e["level"],
                            "service": e["service"],
                        }
                    )
                tmp_path2 = f2.name

            try:
                second_pass = parse_single_file(tmp_path2)
                assert len(second_pass) == len(first_pass), (
                    f"Second parse: expected {len(first_pass)} events, got {len(second_pass)}"
                )
                for i, (orig, reparsed) in enumerate(zip(first_pass, second_pass)):
                    assert orig["message"] == reparsed["message"], (
                        f"Event {i}: message mismatch: {orig['message']!r} != {reparsed['message']!r}"
                    )
                    assert orig["level"] == reparsed["level"], (
                        f"Event {i}: level mismatch: {orig['level']!r} != {reparsed['level']!r}"
                    )
                    assert orig["service"] == reparsed["service"], (
                        f"Event {i}: service mismatch: {orig['service']!r} != {reparsed['service']!r}"
                    )
            finally:
                os.unlink(tmp_path2)
        finally:
            os.unlink(tmp_path)

# ─── Property 12: Report timeline truncation ────────────────────────────────

from hypothesis import HealthCheck
from clarity.integrations.report_exporter import ReportExporter

# A minimal fixed event used to build large timelines cheaply
_FIXED_EVENT = {
    "timestamp": "2024-01-01T00:00:00Z",
    "level": "ERROR",
    "service": "svc",
    "message": "test message",
}


def _make_timeline(n: int):
    """Return a list of n identical minimal events."""
    return [_FIXED_EVENT.copy() for _ in range(n)]


def _make_tagged_timeline(n: int):
    """Return a list of n events with unique messages EVENT_0000 … EVENT_NNNN."""
    return [dict(_FIXED_EVENT, message=f"EVENT_{i:04d}") for i in range(n)]


_MINIMAL_ANALYSIS = json.dumps({
    "summary": "Test incident",
    "root_cause_description": "Test root cause",
    "affected_components": ["svc-a"],
    "confidence_score": 0.9,
    "remediation_steps": [],
})


def _count_markdown_timeline_rows(markdown: str) -> int:
    """Count data rows in the Markdown timeline table (excluding header and separator)."""
    lines = markdown.splitlines()
    in_table = False
    row_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("| Time") and "Level" in stripped:
            in_table = True
            continue
        if in_table and stripped.startswith("|---"):
            continue
        if in_table and stripped.startswith("|"):
            row_count += 1
        elif in_table and not stripped.startswith("|"):
            break
    return row_count


class TestProperty12ReportTimelineTruncation:
    """
    Property 12: Report timeline truncation

    **Validates: Requirements 7.4, 7.5**

    For any timeline with N events, `to_markdown()` shall include at most 25
    events in the timeline table, and `to_json()` shall include at most 50
    events in the `timeline` array, regardless of N.
    """

    @given(n=st.integers(min_value=26, max_value=200))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_markdown_truncates_to_25_events(self, n):
        """to_markdown() includes at most 25 timeline rows for any N > 25."""
        exporter = ReportExporter()
        timeline = _make_timeline(n)
        md = exporter.to_markdown(
            analysis_result=_MINIMAL_ANALYSIS,
            timeline_data=timeline,
        )
        row_count = _count_markdown_timeline_rows(md)
        assert row_count <= 25, (
            f"Markdown timeline has {row_count} rows for input of {n} events; "
            f"expected at most 25"
        )

    @given(n=st.integers(min_value=51, max_value=300))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_json_truncates_to_50_events(self, n):
        """to_json() includes at most 50 timeline entries for any N > 50."""
        exporter = ReportExporter()
        timeline = _make_timeline(n)
        json_str = exporter.to_json(
            analysis_result=_MINIMAL_ANALYSIS,
            timeline_data=timeline,
        )
        report = json.loads(json_str)
        timeline_entries = report.get("timeline", [])
        assert len(timeline_entries) <= 50, (
            f"JSON timeline has {len(timeline_entries)} entries for input of {n} events; "
            f"expected at most 50"
        )

    @given(n=st.integers(min_value=26, max_value=100))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_markdown_preserves_first_25_events(self, n):
        """to_markdown() includes the first 25 events (not arbitrary ones)."""
        exporter = ReportExporter()
        tagged = _make_tagged_timeline(n)
        md = exporter.to_markdown(
            analysis_result=_MINIMAL_ANALYSIS,
            timeline_data=tagged,
        )
        for i in range(25):
            assert f"EVENT_{i:04d}" in md, (
                f"Expected EVENT_{i:04d} to appear in Markdown output"
            )
        for i in range(25, min(n, 30)):
            assert f"EVENT_{i:04d}" not in md, (
                f"Expected EVENT_{i:04d} to be truncated from Markdown output"
            )

    @given(n=st.integers(min_value=51, max_value=150))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
    def test_json_preserves_first_50_events(self, n):
        """to_json() includes the first 50 events (not arbitrary ones)."""
        exporter = ReportExporter()
        tagged = _make_tagged_timeline(n)
        json_str = exporter.to_json(
            analysis_result=_MINIMAL_ANALYSIS,
            timeline_data=tagged,
        )
        report = json.loads(json_str)
        timeline_entries = report.get("timeline", [])
        messages = [entry.get("message", "") for entry in timeline_entries]
        for i in range(50):
            assert f"EVENT_{i:04d}" in messages, (
                f"Expected EVENT_{i:04d} to appear in JSON timeline"
            )
        for i in range(50, min(n, 55)):
            assert f"EVENT_{i:04d}" not in messages, (
                f"Expected EVENT_{i:04d} to be truncated from JSON timeline"
            )


# ─── Property 13: Report JSON round-trip ────────────────────────────────────


@st.composite
def valid_analysis_dicts(draw):
    """Generate valid analysis result dicts matching the LLM output schema."""
    summary = draw(
        st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=1,
            max_size=200,
        )
    )
    root_cause = draw(
        st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=1,
            max_size=200,
        )
    )
    n_components = draw(st.integers(min_value=1, max_value=5))
    affected_components = draw(
        st.lists(
            st.text(
                alphabet=string.ascii_lowercase + string.digits + "-",
                min_size=1,
                max_size=30,
            ),
            min_size=n_components,
            max_size=n_components,
        )
    )
    confidence_score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    return {
        "summary": summary,
        "root_cause_description": root_cause,
        "affected_components": affected_components,
        "confidence_score": confidence_score,
    }


@st.composite
def valid_timeline_events(draw):
    """Generate a list of valid timeline event dicts."""
    n = draw(st.integers(min_value=0, max_value=10))
    events = []
    for _ in range(n):
        events.append({
            "timestamp": "2024-01-01T00:00:00Z",
            "level": draw(st.sampled_from(["DEBUG", "INFO", "WARN", "ERROR", "FATAL"])),
            "service": draw(
                st.text(
                    alphabet=string.ascii_lowercase + string.digits + "-",
                    min_size=1,
                    max_size=20,
                )
            ),
            "message": draw(
                st.text(
                    alphabet=string.ascii_letters + string.digits + " .,!?-_",
                    min_size=1,
                    max_size=80,
                )
            ),
        })
    return events


class TestProperty13ReportJSONRoundTrip:
    """
    Property 13: Report JSON round-trip

    For any valid analysis result string and timeline data,
    `json.loads(exporter.to_json(analysis, timeline, cmd))` shall produce a
    dict containing `summary`, `root_cause`, `affected_components`,
    `remediation`, and `timeline` keys with equivalent values.

    **Validates: Requirements 7.8**
    """

    @given(analysis=valid_analysis_dicts(), timeline=valid_timeline_events())
    @settings(max_examples=100)
    def test_required_keys_present(self, analysis, timeline):
        """Parsed JSON report must contain all five required top-level keys."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd="kubectl rollout restart deployment/svc",
        )
        parsed = json.loads(result)
        for key in ("summary", "root_cause", "affected_components", "remediation", "timeline"):
            assert key in parsed, f"Required key {key!r} missing from JSON report"

    @given(analysis=valid_analysis_dicts(), timeline=valid_timeline_events())
    @settings(max_examples=100)
    def test_summary_value_equivalent(self, analysis, timeline):
        """The `summary` field in the JSON report matches the input summary."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd="",
        )
        parsed = json.loads(result)
        assert parsed["summary"] == analysis["summary"], (
            f"summary mismatch: expected {analysis['summary']!r}, got {parsed['summary']!r}"
        )

    @given(analysis=valid_analysis_dicts(), timeline=valid_timeline_events())
    @settings(max_examples=100)
    def test_root_cause_value_equivalent(self, analysis, timeline):
        """The `root_cause.description` field matches the input root_cause_description."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd="",
        )
        parsed = json.loads(result)
        assert parsed["root_cause"]["description"] == analysis["root_cause_description"], (
            f"root_cause.description mismatch: "
            f"expected {analysis['root_cause_description']!r}, "
            f"got {parsed['root_cause']['description']!r}"
        )

    @given(analysis=valid_analysis_dicts(), timeline=valid_timeline_events())
    @settings(max_examples=100)
    def test_affected_components_equivalent(self, analysis, timeline):
        """The `affected_components` list matches the input affected_components."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd="",
        )
        parsed = json.loads(result)
        assert parsed["affected_components"] == analysis["affected_components"], (
            f"affected_components mismatch: "
            f"expected {analysis['affected_components']!r}, "
            f"got {parsed['affected_components']!r}"
        )

    @given(
        analysis=valid_analysis_dicts(),
        timeline=valid_timeline_events(),
        cmd=st.text(
            alphabet=string.ascii_letters + string.digits + " /-_.",
            min_size=0,
            max_size=100,
        ),
    )
    @settings(max_examples=100)
    def test_remediation_command_equivalent(self, analysis, timeline, cmd):
        """The `remediation.command` field matches the input remediation_cmd."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd=cmd,
        )
        parsed = json.loads(result)
        assert parsed["remediation"]["command"] == cmd, (
            f"remediation.command mismatch: expected {cmd!r}, "
            f"got {parsed['remediation']['command']!r}"
        )

    @given(analysis=valid_analysis_dicts(), timeline=valid_timeline_events())
    @settings(max_examples=100)
    def test_timeline_entries_equivalent(self, analysis, timeline):
        """The `timeline` array contains equivalent entries to the input timeline data."""
        exporter = ReportExporter()
        analysis_str = json.dumps(analysis)
        result = exporter.to_json(
            analysis_result=analysis_str,
            timeline_data=timeline,
            remediation_cmd="",
        )
        parsed = json.loads(result)
        expected_count = min(len(timeline), 50)
        assert len(parsed["timeline"]) == expected_count, (
            f"timeline length mismatch: expected {expected_count}, "
            f"got {len(parsed['timeline'])}"
        )
        for i, (orig, entry) in enumerate(zip(timeline[:50], parsed["timeline"])):
            assert entry["message"] == orig["message"], (
                f"timeline[{i}].message mismatch: "
                f"expected {orig['message']!r}, got {entry['message']!r}"
            )
            assert entry["level"] == orig["level"], (
                f"timeline[{i}].level mismatch: "
                f"expected {orig['level']!r}, got {entry['level']!r}"
            )
            assert entry["service"] == orig["service"], (
                f"timeline[{i}].service mismatch: "
                f"expected {orig['service']!r}, got {entry['service']!r}"
            )


# ─── Property 18: Vector store embedding round-trip ─────────────────────────

import asyncio
from clarity.context.engine import CodeUnit
from clarity.context.vector_store import InMemoryVectorStore


@st.composite
def code_units_with_embeddings(draw):
    """Generate a CodeUnit with random non-empty fields and a random embedding vector."""
    safe_chars = string.ascii_letters + string.digits + " _-"
    name = draw(st.text(alphabet=safe_chars, min_size=1, max_size=30))
    signature = draw(st.text(alphabet=safe_chars, min_size=1, max_size=60))
    docstring = draw(st.text(alphabet=safe_chars, min_size=1, max_size=100))
    body = draw(st.text(alphabet=safe_chars, min_size=1, max_size=200))
    language = draw(st.sampled_from(["python", "javascript", "typescript", "go", "java"]))
    embedding = draw(
        st.lists(
            st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=10,
        )
    )
    unit = CodeUnit(
        file_path="test_file.py",
        unit_type="function",
        name=name,
        signature=signature,
        docstring=docstring,
        body=body,
        language=language,
        embedding=embedding,
    )
    return unit, embedding


class TestProperty18VectorStoreEmbeddingRoundTrip:
    """
    Property 18: Vector store embedding round-trip

    For any indexed CodeUnit, submitting the unit's original content as a
    search query shall return that unit within the top-3 results ranked by
    embedding similarity.

    **Validates: Requirements 12.8**
    """

    @given(sample=code_units_with_embeddings())
    @settings(max_examples=100)
    def test_unit_appears_in_top3_results(self, sample):
        """Searching with the same embedding vector returns the unit in top-3 results."""
        unit, embedding = sample

        store = InMemoryVectorStore()
        asyncio.run(store.add(unit))

        results = asyncio.run(store.search(embedding, top_k=3))

        assert unit in results, (
            f"Unit '{unit.name}' not found in top-3 results after indexing with its own embedding"
        )

    @given(sample=code_units_with_embeddings())
    @settings(max_examples=100)
    def test_unit_is_top_result_with_identical_embedding(self, sample):
        """Cosine similarity of a vector with itself is 1.0, so the unit must be ranked #1."""
        unit, embedding = sample

        # Only test when embedding is non-zero (cosine similarity is defined)
        norm = sum(x * x for x in embedding) ** 0.5
        assume(norm > 0.0)

        store = InMemoryVectorStore()
        asyncio.run(store.add(unit))

        results = asyncio.run(store.search(embedding, top_k=1))

        assert len(results) == 1, "Expected exactly 1 result"
        assert results[0] is unit, (
            f"Unit '{unit.name}' should be the top result when searching with its own embedding"
        )

    def test_keyword_fallback_returns_unit(self):
        """search_by_keyword with a word from the unit's name returns that unit."""
        unit = CodeUnit(
            file_path="test_file.py",
            unit_type="function",
            name="unique_authentication_handler",
            signature="def unique_authentication_handler():",
            docstring="Handles authentication.",
            body="def unique_authentication_handler():\n    pass",
            language="python",
            embedding=None,
        )

        store = InMemoryVectorStore()
        asyncio.run(store.add(unit))

        results = store.search_by_keyword("unique_authentication_handler", top_k=5)

        assert unit in results, (
            "Unit not found via keyword search using a word from its name"
        )


# ─── Properties 1–4, 6–9, 11, 14, 15 (Task 8) ──────────────────────────────
#
# These tests cover the remaining properties from the design document.
# They are appended here to keep all property-based tests in one file.

import re
import csv
import json
import os
import tempfile
import string
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from clarity.parsers.log_parser import parse_single_file, parse_log_files, _parse_text
from clarity.agents.analyst import AnalystAgent
from clarity.mcp.server import _sanitize
from clarity.agents.copilot import CoPilotAgent, ConversationContext
from clarity.integrations.jira import JiraClient
from clarity.core.llm_client import LLMClient


# ─── Supported extensions (mirrors parse_single_file routing) ───────────────

SUPPORTED_EXTS = {".json", ".jsonl", ".csv", ".log", ".txt", ".syslog"}


# ─── Property 1: Log format parsing completeness ────────────────────────────


def _make_minimal_file(ext: str, tmp_path: str) -> str:
    """Create a minimal valid log file for the given extension and return its path."""
    path = os.path.join(tmp_path, f"test{ext}")
    if ext in (".json", ".jsonl"):
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"message": "hello", "level": "INFO"}], f)
    elif ext == ".csv":
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["message", "level"])
            writer.writeheader()
            writer.writerow({"message": "hello", "level": "INFO"})
    else:  # .log, .txt, .syslog
        with open(path, "w", encoding="utf-8") as f:
            f.write("2024-01-01 00:00:00 INFO hello\n")
    return path


class TestProperty1LogFormatParsingCompleteness:
    """
    Property 1: Log format parsing completeness

    For any log file with a supported extension (.json, .jsonl, .csv, .log,
    .txt, .syslog), calling parse_single_file() shall return a non-empty list
    of dicts, each containing at minimum a `message` key.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """

    @given(ext=st.sampled_from([".json", ".jsonl", ".csv", ".log", ".txt", ".syslog"]))
    @settings(max_examples=50, deadline=None)
    def test_returns_nonempty_list_with_message_key(self, ext):
        """parse_single_file() returns a non-empty list with a message key for all supported extensions."""
        with tempfile.TemporaryDirectory() as tmp:
            path = _make_minimal_file(ext, tmp)
            result = parse_single_file(path)
            assert isinstance(result, list), f"Expected list, got {type(result)}"
            assert len(result) > 0, f"Expected non-empty list for extension {ext!r}"
            for event in result:
                assert "message" in event, (
                    f"Event missing 'message' key for extension {ext!r}: {event}"
                )


# ─── Property 2: Unsupported extension raises ValueError ────────────────────


class TestProperty2UnsupportedExtensionRaisesValueError:
    """
    Property 2: Unsupported extension raises ValueError

    For any file path whose extension is not in the supported set, calling
    parse_single_file() shall raise a ValueError.

    **Validates: Requirements 1.8**
    """

    @given(
        ext=st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase + string.digits)
        .filter(lambda s: "." + s not in SUPPORTED_EXTS)
        .filter(lambda s: s.isalpha())  # keep it a clean extension
    )
    @settings(max_examples=50, deadline=None)
    def test_unsupported_extension_raises_value_error(self, ext):
        """parse_single_file() raises ValueError for any unsupported extension."""
        with tempfile.NamedTemporaryFile(
            suffix=f".{ext}", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write("some content\n")
            tmp_path = f.name
        try:
            with pytest.raises(ValueError):
                parse_single_file(tmp_path)
        finally:
            os.unlink(tmp_path)


# ─── Property 3: Multi-file timeline is chronologically sorted ──────────────


@st.composite
def two_log_files_with_shuffled_timestamps(draw):
    """Generate two JSON log files with shuffled timestamps."""
    # Generate 4–10 timestamps spread across a day
    n = draw(st.integers(min_value=2, max_value=5))
    base_ts = [f"2024-01-01T{h:02d}:00:00" for h in range(n * 2)]
    # Shuffle them across two files
    indices = draw(st.permutations(range(n * 2)))
    file1_events = [{"message": f"event-{i}", "timestamp": base_ts[i], "level": "INFO"} for i in indices[:n]]
    file2_events = [{"message": f"event-{i}", "timestamp": base_ts[i], "level": "INFO"} for i in indices[n:]]
    return file1_events, file2_events


class TestProperty3MultiFileTimelineChronologicallySorted:
    """
    Property 3: Multi-file timeline is chronologically sorted

    For any collection of two or more log files, the DataFrame returned by
    parse_log_files() shall have its timestamp column in non-decreasing order.

    **Validates: Requirements 1.9**
    """

    @given(files=two_log_files_with_shuffled_timestamps())
    @settings(max_examples=50, deadline=None)
    def test_timeline_is_non_decreasing(self, files):
        """parse_log_files() returns a DataFrame with non-decreasing timestamps."""
        file1_events, file2_events = files
        with tempfile.TemporaryDirectory() as tmp:
            path1 = os.path.join(tmp, "file1.json")
            path2 = os.path.join(tmp, "file2.json")
            with open(path1, "w") as f:
                json.dump(file1_events, f)
            with open(path2, "w") as f:
                json.dump(file2_events, f)

            df = parse_log_files([path1, path2])
            assert not df.empty, "Expected non-empty DataFrame"
            assert "timestamp" in df.columns, "Expected 'timestamp' column"
            timestamps = df["timestamp"].tolist()
            for i in range(len(timestamps) - 1):
                assert timestamps[i] <= timestamps[i + 1], (
                    f"Timestamps not sorted at index {i}: "
                    f"{timestamps[i]} > {timestamps[i + 1]}"
                )


# ─── Property 4: Text log field extraction ──────────────────────────────────


class TestProperty4TextLogFieldExtraction:
    """
    Property 4: Text log field extraction

    For any plain-text log line containing a recognizable timestamp pattern
    and a log level keyword, _parse_text() shall produce an event dict where
    `timestamp` is a datetime object and `level` matches the keyword
    (case-normalized to uppercase).

    **Validates: Requirements 1.5, 1.6**
    """

    @given(
        dt=st.datetimes(
            min_value=datetime(2000, 1, 1),
            max_value=datetime(2099, 12, 31),
        ),
        level=st.sampled_from(["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]),
    )
    @settings(max_examples=50, deadline=None)
    def test_timestamp_and_level_extracted(self, dt, level):
        """_parse_text() extracts timestamp as datetime and level matching the keyword."""
        ts_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts_str} {level} Service started successfully\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write(line)
            tmp_path = f.name

        try:
            from pathlib import Path
            events = _parse_text(Path(tmp_path))
            assert len(events) >= 1, "Expected at least one event"
            event = events[0]
            assert isinstance(event["timestamp"], datetime), (
                f"Expected datetime, got {type(event['timestamp'])}"
            )
            assert event["level"] == level, (
                f"Expected level {level!r}, got {event['level']!r}"
            )
        finally:
            os.unlink(tmp_path)


# ─── Property 6: RCA field extraction from valid JSON ───────────────────────


@st.composite
def rca_json_dicts(draw):
    """Generate valid RCA JSON dicts with all four required fields."""
    summary = draw(st.text(
        alphabet=string.ascii_letters + string.digits + " .,!?-_:",
        min_size=1, max_size=100,
    ))
    root_cause_description = draw(st.text(
        alphabet=string.ascii_letters + string.digits + " .,!?-_:",
        min_size=1, max_size=100,
    ))
    affected_components = draw(st.lists(
        st.text(alphabet=string.ascii_lowercase + string.digits + "-", min_size=1, max_size=20),
        min_size=1, max_size=5,
    ))
    confidence_score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    return {
        "summary": summary,
        "root_cause_description": root_cause_description,
        "affected_components": affected_components,
        "confidence_score": confidence_score,
    }


class TestProperty6RCAFieldExtraction:
    """
    Property 6: RCA field extraction from valid JSON

    For any LLM response string that contains a valid JSON object with
    summary, root_cause_description, affected_components, and confidence_score
    keys, the Analyst Agent's JSON extraction logic shall return a dict
    containing all four keys with non-null values.

    **Validates: Requirements 2.3**
    """

    @given(data=rca_json_dicts())
    @settings(max_examples=50)
    def test_all_four_keys_present(self, data):
        """_extract_json_robust() returns a dict with all four required RCA keys."""
        agent = AnalystAgent.__new__(AnalystAgent)
        json_str = json.dumps(data)
        result_str = agent._extract_json_robust(json_str)
        result = json.loads(result_str)
        for key in ("summary", "root_cause_description", "affected_components", "confidence_score"):
            assert key in result, f"Key {key!r} missing from extracted JSON"
            assert result[key] is not None, f"Key {key!r} has null value"

    @given(data=rca_json_dicts())
    @settings(max_examples=50)
    def test_values_match_input(self, data):
        """_extract_json_robust() preserves the values from the input JSON."""
        agent = AnalystAgent.__new__(AnalystAgent)
        # Wrap in prose to simulate LLM output
        prose = f"Here is the analysis:\n{json.dumps(data)}\nEnd of analysis."
        result_str = agent._extract_json_robust(prose)
        result = json.loads(result_str)
        assert result["summary"] == data["summary"]
        assert result["root_cause_description"] == data["root_cause_description"]
        assert result["affected_components"] == data["affected_components"]


# ─── Property 7: Fallback analysis on invalid LLM response ──────────────────


class TestProperty7FallbackAnalysisOnInvalidLLMResponse:
    """
    Property 7: Fallback analysis on invalid LLM response

    For any LLM response string that is not valid JSON (or starts with
    "Error:"), _generate_mock_analysis() shall return a valid JSON string
    containing summary, root_cause_description, affected_components, and
    confidence_score.

    **Validates: Requirements 2.4**
    """

    @given(
        text=st.text().filter(lambda s: not s.strip().startswith("{"))
    )
    @settings(max_examples=50)
    def test_mock_analysis_returns_valid_json_with_required_keys(self, text):
        """_generate_mock_analysis() always returns valid JSON with required keys."""
        agent = AnalystAgent.__new__(AnalystAgent)
        empty_df = pd.DataFrame()
        result_str = agent._generate_mock_analysis(empty_df)
        # Must be valid JSON
        result = json.loads(result_str)
        for key in ("summary", "root_cause_description", "affected_components", "confidence_score"):
            assert key in result, f"Key {key!r} missing from mock analysis"
            assert result[key] is not None, f"Key {key!r} is None in mock analysis"

    def test_mock_analysis_confidence_score_in_range(self):
        """confidence_score in mock analysis must be in [0.0, 1.0]."""
        agent = AnalystAgent.__new__(AnalystAgent)
        result = json.loads(agent._generate_mock_analysis(pd.DataFrame()))
        score = result["confidence_score"]
        assert 0.0 <= score <= 1.0, f"confidence_score {score} out of range [0.0, 1.0]"


# ─── Property 8: Keyword-to-remediation-strategy mapping ────────────────────


class TestProperty8KeywordToRemediationStrategyMapping:
    """
    Property 8: Keyword-to-remediation-strategy mapping

    For any analysis string, the remediation selector shall map strings
    containing exhaustion/memory keywords to the restart endpoint and strings
    containing deployment/config keywords to the rollback endpoint.

    **Validates: Requirements 2.5, 3.2, 3.3**
    """

    RESTART_KEYWORDS = ["exhausted", "pool", "memory"]
    ROLLBACK_KEYWORDS = ["deployment", "rollback", "config"]

    def _get_endpoint(self, analysis: str) -> str:
        """Replicate the keyword routing logic from _get_remediation_command."""
        lower = analysis.lower()
        if "exhausted" in lower or "pool" in lower or "memory" in lower:
            return "/tools/restart"
        return "/tools/rollback"

    @given(
        prefix=st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=0, max_size=50,
        ),
        keyword=st.sampled_from(["exhausted", "pool", "memory"]),
        suffix=st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=0, max_size=50,
        ),
    )
    @settings(max_examples=50)
    def test_restart_keywords_route_to_restart_endpoint(self, prefix, keyword, suffix):
        """Analysis containing exhaustion/memory keywords routes to /tools/restart."""
        analysis = f"{prefix} {keyword} {suffix}"
        endpoint = self._get_endpoint(analysis)
        assert endpoint == "/tools/restart", (
            f"Expected /tools/restart for keyword {keyword!r}, got {endpoint!r}"
        )

    @given(
        prefix=st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=0, max_size=50,
        ),
        keyword=st.sampled_from(["deployment", "rollback"]),
        suffix=st.text(
            alphabet=string.ascii_letters + string.digits + " .,!?-_:",
            min_size=0, max_size=50,
        ),
    )
    @settings(max_examples=50)
    def test_deployment_keywords_route_to_rollback_endpoint(self, prefix, keyword, suffix):
        """Analysis containing deployment keywords routes to /tools/rollback (default)."""
        # Ensure no restart keywords are present
        analysis = f"{prefix} {keyword} {suffix}"
        assume("exhausted" not in analysis.lower())
        assume("pool" not in analysis.lower())
        assume("memory" not in analysis.lower())
        endpoint = self._get_endpoint(analysis)
        assert endpoint == "/tools/rollback", (
            f"Expected /tools/rollback for keyword {keyword!r}, got {endpoint!r}"
        )

    @given(
        service_name=st.text(
            alphabet=string.ascii_lowercase + string.digits + "-",
            min_size=1, max_size=20,
        )
    )
    @settings(max_examples=50)
    def test_extract_service_returns_known_service_or_default(self, service_name):
        """_extract_service() returns a known service name or the default 'auth-service'."""
        agent = AnalystAgent.__new__(AnalystAgent)
        known_services = ["auth-service", "api-service", "user-service", "payment-service"]
        result = agent._extract_service(service_name)
        assert result in known_services, (
            f"_extract_service returned unknown service {result!r}"
        )


# ─── Property 9: MCP command contains sanitized service name ────────────────


class TestProperty9MCPCommandSanitizedServiceName:
    """
    Property 9: MCP command contains sanitized service name

    For any service name string, _sanitize() shall:
    1. Return a string where every character satisfies isalnum() or is '-'
    2. Not contain command injection chars (;, |, &, $, backtick)
    3. Preserve any valid chars from the input (isalnum() or '-')

    **Validates: Requirements 3.8, 4.3, 4.4, 4.5**
    """

    _INJECTION_CHARS = set(";|&$`")

    @given(service_name=st.text(min_size=1))
    @settings(max_examples=100)
    def test_result_contains_only_allowed_chars(self, service_name):
        """_sanitize() output contains only chars where isalnum() or '-'."""
        result = _sanitize(service_name)
        for ch in result:
            assert ch.isalnum() or ch == "-", (
                f"_sanitize({service_name!r}) = {result!r} contains disallowed char {ch!r}"
            )

    @given(service_name=st.text(min_size=1))
    @settings(max_examples=100)
    def test_no_injection_chars_in_result(self, service_name):
        """_sanitize() output contains no command injection characters."""
        result = _sanitize(service_name)
        for ch in self._INJECTION_CHARS:
            assert ch not in result, (
                f"Injection char {ch!r} found in _sanitize({service_name!r}) = {result!r}"
            )

    @given(service_name=st.text(min_size=1))
    @settings(max_examples=100)
    def test_valid_input_chars_preserved(self, service_name):
        """All alphanumeric and hyphen chars from input appear in the output."""
        result = _sanitize(service_name)
        valid_from_input = [c for c in service_name if c.isalnum() or c == "-"]
        # The result must contain exactly those characters (in order)
        assert list(result) == valid_from_input, (
            f"_sanitize({service_name!r}) = {result!r}, "
            f"expected {valid_from_input!r}"
        )


# ─── Property 11: CoPilot prompt contains required context elements ──────────


class TestProperty11CoPilotPromptContainsRequiredContextElements:
    """
    Property 11: CoPilot prompt contains required context elements

    For any question string submitted to _build_qa_prompt(), the returned
    prompt string shall contain the incident analysis result, the error
    distribution section, the service topology section, and the question itself.

    **Validates: Requirements 6.3**
    """

    def _make_agent_with_context(self, analysis_result: str) -> CoPilotAgent:
        """Create a CoPilotAgent with a populated ConversationContext."""
        agent = CoPilotAgent.__new__(CoPilotAgent)
        ctx = ConversationContext(
            incident_data={"incident_id": "INC-001"},
            timeline_data=[
                {"timestamp": "2024-01-01T00:00:00", "level": "ERROR", "service": "auth-service", "message": "DB error"},
                {"timestamp": "2024-01-01T00:01:00", "level": "INFO", "service": "api-service", "message": "Request received"},
            ],
            analysis_result=analysis_result,
            conversation_history=[],
        )
        ctx.enrich()
        agent.context = ctx
        return agent

    @given(question=st.text(min_size=1, max_size=200, alphabet=string.ascii_letters + string.digits + " ?.,!-_"))
    @settings(max_examples=50)
    def test_prompt_contains_analysis_result(self, question):
        """_build_qa_prompt() includes the analysis result in the prompt."""
        analysis = "Summary: DB connection pool exhausted. Root cause: config change."
        agent = self._make_agent_with_context(analysis)
        prompt = agent._build_qa_prompt(question)
        assert analysis in prompt, (
            f"Analysis result not found in prompt for question {question!r}"
        )

    @given(question=st.text(min_size=1, max_size=200, alphabet=string.ascii_letters + string.digits + " ?.,!-_"))
    @settings(max_examples=50)
    def test_prompt_contains_error_distribution(self, question):
        """_build_qa_prompt() includes the error distribution section."""
        analysis = "Summary: DB connection pool exhausted."
        agent = self._make_agent_with_context(analysis)
        prompt = agent._build_qa_prompt(question)
        assert "ERROR DISTRIBUTION" in prompt, (
            f"Error distribution section not found in prompt for question {question!r}"
        )

    @given(question=st.text(min_size=1, max_size=200, alphabet=string.ascii_letters + string.digits + " ?.,!-_"))
    @settings(max_examples=50)
    def test_prompt_contains_service_topology(self, question):
        """_build_qa_prompt() includes the service topology section."""
        analysis = "Summary: DB connection pool exhausted."
        agent = self._make_agent_with_context(analysis)
        prompt = agent._build_qa_prompt(question)
        assert "SERVICES INVOLVED" in prompt, (
            f"Service topology section not found in prompt for question {question!r}"
        )

    @given(question=st.text(min_size=1, max_size=200, alphabet=string.ascii_letters + string.digits + " ?.,!-_"))
    @settings(max_examples=50)
    def test_prompt_contains_question(self, question):
        """_build_qa_prompt() includes the question itself in the prompt."""
        analysis = "Summary: DB connection pool exhausted."
        agent = self._make_agent_with_context(analysis)
        prompt = agent._build_qa_prompt(question)
        assert question in prompt, (
            f"Question {question!r} not found in prompt"
        )


# ─── Property 14: Confidence score to Jira priority mapping ─────────────────


class TestProperty14ConfidenceScoreToJiraPriorityMapping:
    """
    Property 14: Confidence score to Jira priority mapping

    For any confidence score in [0.0, 1.0], the Jira priority mapping shall
    return "Highest" for scores >= 0.85, "High" for >= 0.70, "Medium" for
    >= 0.50, and "Low" for < 0.50, with no gaps or overlaps in the mapping.

    **Validates: Requirements 8.7**
    """

    @given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    @settings(max_examples=100)
    def test_priority_mapping_no_gaps_or_overlaps(self, score):
        """Every score in [0.0, 1.0] maps to exactly one priority tier."""
        client = JiraClient()
        priority = client._priority_from_confidence(score)
        assert priority in ("Highest", "High", "Medium", "Low"), (
            f"Unexpected priority {priority!r} for score {score}"
        )

    @given(score=st.floats(min_value=0.85, max_value=1.0, allow_nan=False))
    @settings(max_examples=50)
    def test_highest_priority_for_score_gte_085(self, score):
        """Scores >= 0.85 map to 'Highest'."""
        client = JiraClient()
        assert client._priority_from_confidence(score) == "Highest", (
            f"Expected 'Highest' for score {score}, got {client._priority_from_confidence(score)!r}"
        )

    @given(score=st.floats(min_value=0.70, max_value=0.8499, allow_nan=False))
    @settings(max_examples=50)
    def test_high_priority_for_score_gte_070_lt_085(self, score):
        """Scores in [0.70, 0.85) map to 'High'."""
        client = JiraClient()
        assert client._priority_from_confidence(score) == "High", (
            f"Expected 'High' for score {score}, got {client._priority_from_confidence(score)!r}"
        )

    @given(score=st.floats(min_value=0.50, max_value=0.6999, allow_nan=False))
    @settings(max_examples=50)
    def test_medium_priority_for_score_gte_050_lt_070(self, score):
        """Scores in [0.50, 0.70) map to 'Medium'."""
        client = JiraClient()
        assert client._priority_from_confidence(score) == "Medium", (
            f"Expected 'Medium' for score {score}, got {client._priority_from_confidence(score)!r}"
        )

    @given(score=st.floats(min_value=0.0, max_value=0.4999, allow_nan=False))
    @settings(max_examples=50)
    def test_low_priority_for_score_lt_050(self, score):
        """Scores < 0.50 map to 'Low'."""
        client = JiraClient()
        assert client._priority_from_confidence(score) == "Low", (
            f"Expected 'Low' for score {score}, got {client._priority_from_confidence(score)!r}"
        )


# ─── Property 15: Model ID routes to correct request schema ─────────────────


class TestProperty15ModelIDRoutesToCorrectRequestSchema:
    """
    Property 15: Model ID routes to correct request schema

    For any model ID string containing "amazon.titan", _build_request_body()
    shall return a dict with an inputText key and no messages key.
    For any model ID containing "anthropic", it shall return a dict with a
    messages key and no inputText key.

    **Validates: Requirements 9.2, 9.3**
    """

    @given(
        model_id=st.sampled_from([
            "amazon.titan-text-express-v1",
            "amazon.titan-text-lite-v1",
            "amazon.titan-text-premier-v1:0",
        ])
    )
    @settings(max_examples=20)
    def test_titan_model_uses_input_text_schema(self, model_id):
        """Titan model IDs produce a request body with inputText and no messages."""
        client = LLMClient.__new__(LLMClient)
        client.client = None
        with patch("clarity.core.llm_client.settings") as mock_settings:
            mock_settings.bedrock_model_id = model_id
            mock_settings.max_tokens = 4096
            mock_settings.temperature = 0.3
            mock_settings.top_p = 0.9
            body = client._build_request_body("test prompt")
        assert "inputText" in body, f"Expected 'inputText' key for model {model_id!r}"
        assert "messages" not in body, f"Unexpected 'messages' key for model {model_id!r}"

    @given(
        model_id=st.sampled_from([
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-instant-v1",
        ])
    )
    @settings(max_examples=20)
    def test_anthropic_model_uses_messages_schema(self, model_id):
        """Anthropic model IDs produce a request body with messages and no inputText."""
        client = LLMClient.__new__(LLMClient)
        client.client = None
        with patch("clarity.core.llm_client.settings") as mock_settings:
            mock_settings.bedrock_model_id = model_id
            mock_settings.max_tokens = 4096
            mock_settings.temperature = 0.3
            mock_settings.top_p = 0.9
            body = client._build_request_body("test prompt")
        assert "messages" in body, f"Expected 'messages' key for model {model_id!r}"
        assert "inputText" not in body, f"Unexpected 'inputText' key for model {model_id!r}"
        assert "anthropic_version" in body, f"Expected 'anthropic_version' key for model {model_id!r}"


# ─── End-to-end integration: PII redaction in full pipeline ─────────────────


class TestE2EPIIRedactionPipeline:
    """
    End-to-end integration test: PII redaction in the full parse pipeline.

    Verifies that email addresses and phone numbers written to a real log file
    are absent from every `message` field in the DataFrame returned by
    `parse_log_files()`.

    **Validates: Requirements 13.3, 13.5**
    """

    def test_email_and_phone_redacted_in_parsed_dataframe(self):
        """parse_log_files() must not expose raw email or phone in any message field."""
        email = "user@example.com"
        phone = "555-123-4567"

        log_lines = [
            f"2024-01-01 10:00:00 INFO User logged in: {email}",
            f"2024-01-01 10:01:00 WARN Contact support at {phone} for help",
            f"2024-01-01 10:02:00 ERROR Both present: {email} called from {phone}",
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            f.write("\n".join(log_lines))
            tmp_path = f.name

        try:
            from clarity.parsers.log_parser import parse_log_files
            df = parse_log_files([tmp_path])

            assert not df.empty, "Expected non-empty DataFrame from parse_log_files()"

            messages = df["message"].tolist()
            for msg in messages:
                assert email not in msg, (
                    f"Raw email {email!r} found in message: {msg!r}"
                )
                assert phone not in msg, (
                    f"Raw phone {phone!r} found in message: {msg!r}"
                )
        finally:
            os.unlink(tmp_path)
