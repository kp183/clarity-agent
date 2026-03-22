"""
Append-only audit log for Clarity.

Writes JSON Lines entries to ``audit.log`` recording every significant
action taken by the CLI or API, along with its outcome and the user
context that triggered it.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

_AUDIT_LOG_PATH = Path("audit.log")


def write_audit_log(
    action: str,
    outcome: str,
    user_context: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single JSON Lines entry to *audit.log*.

    Parameters
    ----------
    action:
        Short description of what was performed (e.g. ``"analyze"``,
        ``"remediation_displayed"``).
    outcome:
        Result of the action (e.g. ``"success"``, ``"skipped"``,
        ``"error: <msg>"``).
    user_context:
        Arbitrary dict with caller-supplied metadata (username, session
        id, log files analysed, …).  Defaults to an empty dict.
    """
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "action": action,
        "user_context": user_context or {},
        "outcome": outcome,
    }
    with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
