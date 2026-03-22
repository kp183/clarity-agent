"""Tests for the Analyst Agent."""

import json
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock

from clarity.agents.analyst import AnalystAgent


@pytest.fixture
def agent():
    with patch("clarity.agents.analyst.llm_client"):
        return AnalystAgent()


@pytest.fixture
def sample_df():
    return pd.DataFrame([
        {"timestamp": datetime(2024, 1, 15, 10, 30, 0), "level": "ERROR", "service": "auth-service", "message": "Pool exhausted"},
        {"timestamp": datetime(2024, 1, 15, 10, 30, 1), "level": "INFO", "service": "api-gateway", "message": "Health check ok"},
        {"timestamp": datetime(2024, 1, 15, 10, 30, 2), "level": "ERROR", "service": "auth-service", "message": "Connection timeout"},
        {"timestamp": datetime(2024, 1, 15, 10, 30, 3), "level": "WARN", "service": "database", "message": "Slow query"},
    ])


class TestMockAnalysis:
    def test_generates_valid_json(self, agent, sample_df):
        result = agent._generate_mock_analysis(sample_df)
        data = json.loads(result)
        assert "summary" in data
        assert "root_cause_description" in data
        assert "affected_components" in data
        assert "confidence_score" in data
        assert 0 <= data["confidence_score"] <= 1

    def test_counts_errors(self, agent, sample_df):
        result = agent._generate_mock_analysis(sample_df)
        data = json.loads(result)
        assert "2 errors" in data["summary"]  # 2 ERROR events

    def test_handles_empty_df(self, agent):
        empty_df = pd.DataFrame()
        result = agent._generate_mock_analysis(empty_df)
        data = json.loads(result)
        assert "0 errors" in data["summary"]


class TestServiceExtraction:
    def test_extracts_known_service(self, agent):
        assert agent._extract_service("auth-service failed") == "auth-service"
        assert agent._extract_service("payment-service timeout") == "payment-service"

    def test_default_service(self, agent):
        assert agent._extract_service("something unknown") == "auth-service"


class TestJsonValidation:
    def test_valid_json(self, agent):
        assert agent._is_valid_json('{"key": "value"}')

    def test_invalid_json(self, agent):
        assert not agent._is_valid_json("not json")

    def test_json_in_text(self, agent):
        assert agent._is_valid_json('Here is the result: {"key": "value"} end')

    def test_empty_string(self, agent):
        assert not agent._is_valid_json("")


class TestJsonExtraction:
    def test_clean_json(self, agent):
        result = agent._extract_json_robust('{"summary": "test"}')
        data = json.loads(result)
        assert data["summary"] == "test"

    def test_json_in_markdown(self, agent):
        text = '```json\n{"summary": "test"}\n```'
        result = agent._extract_json_robust(text)
        data = json.loads(result)
        assert data["summary"] == "test"

    def test_json_with_surrounding_text(self, agent):
        text = 'Here is my analysis:\n{"summary": "test", "confidence": 0.9}\nHope this helps!'
        result = agent._extract_json_robust(text)
        data = json.loads(result)
        assert data["summary"] == "test"

    def test_unparseable_returns_error(self, agent):
        result = agent._extract_json_robust("completely garbage text")
        data = json.loads(result)
        assert "error" in data


class TestCoPilotIntegration:
    def test_no_data_before_analysis(self, agent):
        assert agent.get_analysis_data_for_copilot() is None

    def test_data_available_after_analysis(self, agent, sample_df):
        agent.last_analysis_data = {
            "timeline_df": sample_df,
            "analysis_result": '{"summary": "test"}',
            "remediation_command": "kubectl restart",
            "log_files": ["test.log"],
        }
        data = agent.get_analysis_data_for_copilot()
        assert data is not None
        assert len(data["timeline_data"]) == 4
        assert data["analysis_result"] == '{"summary": "test"}'
