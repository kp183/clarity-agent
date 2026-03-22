"""Tests for the Sentinel Agent."""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock

from clarity.agents.sentinel import SentinelAgent
from clarity.core.models import TrendType, AlertSeverity


@pytest.fixture
def agent():
    return SentinelAgent()


@pytest.fixture
def normal_df():
    return pd.DataFrame([
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
    ])


@pytest.fixture
def error_df():
    return pd.DataFrame([
        {"timestamp": datetime.now(), "level": "ERROR", "service": "api", "message": "fail"},
        {"timestamp": datetime.now(), "level": "ERROR", "service": "api", "message": "fail"},
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
        {"timestamp": datetime.now(), "level": "INFO", "service": "api", "message": "ok"},
    ])


class TestSentinelTrendDetection:
    def test_no_alerts_on_normal_traffic(self, agent, normal_df):
        alerts = agent._detect_trends(normal_df)
        assert len(alerts) == 0

    def test_alert_on_high_error_rate(self, agent, error_df):
        # 50% error rate — exceeds 0.25 threshold, so CRITICAL
        alerts = agent._detect_trends(error_df)
        assert len(alerts) == 1
        assert alerts[0].trend_type == TrendType.INCREASING_ERRORS
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_handles_empty_dataframe(self, agent):
        alerts = agent._detect_trends(pd.DataFrame())
        assert len(alerts) == 0

    def test_handles_missing_level_column(self, agent):
        df = pd.DataFrame([{"timestamp": datetime.now(), "message": "test"}])
        alerts = agent._detect_trends(df)
        assert len(alerts) == 0


@pytest.mark.asyncio
class TestSentinelScanning:
    @patch("clarity.agents.sentinel.parse_log_files")
    async def test_scan_with_empty_logs(self, mock_parse, agent):
        mock_parse.return_value = pd.DataFrame()
        result = await agent._scan(["dummy.log"])
        assert result.events_processed == 0
        assert result.status == "no_data"

    @patch("clarity.agents.sentinel.parse_log_files")
    async def test_scan_with_errors(self, mock_parse, agent, error_df):
        mock_parse.return_value = error_df
        result = await agent._scan(["dummy.log"])
        assert result.events_processed == 4
        assert len(result.trends_detected) == 1
        assert result.status == "success"

    @patch("clarity.agents.sentinel.parse_log_files")
    async def test_scan_exception_handling(self, mock_parse, agent):
        mock_parse.side_effect = Exception("Parsing failed")
        result = await agent._scan(["dummy.log"])
        assert "error" in result.status
