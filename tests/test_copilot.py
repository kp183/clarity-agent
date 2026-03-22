"""Tests for the Co-Pilot Agent."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from clarity.agents.copilot import CoPilotAgent, ConversationContext


@pytest.fixture
def agent():
    with patch("clarity.agents.copilot.llm_client"):
        return CoPilotAgent()


@pytest.fixture
def sample_context():
    return ConversationContext(
        incident_data={"log_files": ["test.log"]},
        timeline_data=[
            {"timestamp": "2024-01-01 10:00", "level": "ERROR", "message": "DB failed"},
            {"timestamp": "2024-01-01 10:01", "level": "INFO", "message": "Restarting"},
        ],
        analysis_result='{"summary": "DB issue"}',
    )


class TestCoPilotFallbacks:
    def test_timeline_answer(self, agent, sample_context):
        agent.context = sample_context
        answer = agent._rule_based_answer("Show me the timeline")
        assert "DB failed" in answer
        assert "ERROR" in answer

    def test_error_answer(self, agent, sample_context):
        agent.context = sample_context
        answer = agent._rule_based_answer("What errors occurred?")
        assert "Found 1 error events" in answer
        assert "DB failed" in answer
        assert "Restarting" not in answer  # INFO level should be excluded

    def test_root_cause_answer(self, agent, sample_context):
        agent.context = sample_context
        answer = agent._rule_based_answer("What is the root cause?")
        assert "issue" in answer.lower()

    def test_prevention_answer(self, agent, sample_context):
        agent.context = sample_context
        answer = agent._rule_based_answer("How to prevent this?")
        assert "monitor" in answer.lower()
        assert "circuit breaker" in answer.lower()

    def test_unknown_question_fallback(self, agent, sample_context):
        agent.context = sample_context
        answer = agent._rule_based_answer("What's the weather like?")
        assert "I can help you with:" in answer


class TestCoPilotPromptGeneration:
    def test_prompt_includes_context(self, agent, sample_context):
        agent.context = sample_context
        prompt = agent._build_qa_prompt("Why did it fail?")
        assert "DB issue" in prompt
        assert "DB failed" in prompt
        assert "Why did it fail?" in prompt


class TestCoPilotExport:
    def test_export_empty_without_session(self, agent):
        assert agent.export_conversation() == {}

    def test_export_with_session(self, agent, sample_context):
        agent.context = sample_context
        agent.context.conversation_history = [
            {"question": "Q1", "answer": "A1", "timestamp": "now"}
        ]
        
        data = agent.export_conversation()
        assert "session_start" in data
        assert "session_end" in data
        assert data["questions_count"] == 1
        assert len(data["history"]) == 1
