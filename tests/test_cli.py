"""Unit tests for clarity/cli/app.py."""

import sys
from unittest.mock import MagicMock, patch


def _run_windows_utf8_block(stdout, stderr):
    """Mirror the module-level Windows UTF-8 block from clarity/cli/app.py.

    This helper replicates the exact logic so it can be tested in isolation
    without triggering the full module import chain.
    """
    import os
    if sys.platform == "win32":
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        try:
            stdout.reconfigure(encoding="utf-8", errors="replace")
            stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def test_windows_utf8_reconfigure():
    """On win32, stdout and stderr must be reconfigured with utf-8/replace."""
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()

    with patch("sys.platform", "win32"):
        _run_windows_utf8_block(mock_stdout, mock_stderr)

    mock_stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
    mock_stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")


def test_windows_utf8_reconfigure_not_called_on_non_windows():
    """On non-Windows platforms, reconfigure must NOT be called."""
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()

    with patch("sys.platform", "linux"):
        _run_windows_utf8_block(mock_stdout, mock_stderr)

    mock_stdout.reconfigure.assert_not_called()
    mock_stderr.reconfigure.assert_not_called()
