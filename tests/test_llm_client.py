"""Tests for LLM Client."""

import pytest
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import ClientError
from clarity.core.llm_client import LLMClient, TRANSIENT_ERRORS


@pytest.fixture
def llm_client():
    with patch("clarity.core.llm_client.boto3.client"):
        client = LLMClient()
        # Mock the internal bedrock_runtime client
        client.client = MagicMock()
        return client


class TestLLMClient:
    def test_invoke_success(self, llm_client):
        # Mock a successful response matching AWS Bedrock format for Titan
        # titan responses usually return a byte stream of JSON
        import json
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "results": [{"outputText": "test output JSON data"}]
        }).encode("utf-8")
        
        llm_client.client.invoke_model.return_value = mock_response
        
        result = llm_client.invoke("test prompt")
        assert result == "test output JSON data"

    def test_invoke_failure(self, llm_client):
        # Non-transient ClientError should return an error string immediately
        error_response = {"Error": {"Code": "ValidationException", "Message": "Bad request"}}
        llm_client.client.invoke_model.side_effect = ClientError(error_response, "InvokeModel")

        result = llm_client.invoke("test prompt")
        assert "Error:" in result

    def test_invoke_transient_error_retries_and_exhausts(self, llm_client):
        # Transient error should retry up to max_retries; on last attempt returns the error
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        llm_client.client.invoke_model.side_effect = ClientError(error_response, "InvokeModel")

        with patch("clarity.core.llm_client.time.sleep") as mock_sleep:
            result = llm_client.invoke("test prompt", max_retries=3)

        assert "Error:" in result
        assert llm_client.client.invoke_model.call_count == 3
        # Should have slept twice (after attempt 0 and 1, not after the last attempt)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # 2**0
        mock_sleep.assert_any_call(2)  # 2**1

    def test_invoke_transient_error_succeeds_on_retry(self, llm_client):
        import json
        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_response = {"body": MagicMock()}
        mock_response["body"].read.return_value = json.dumps({
            "results": [{"outputText": "retry success"}]
        }).encode("utf-8")

        llm_client.client.invoke_model.side_effect = [
            ClientError(error_response, "InvokeModel"),
            mock_response,
        ]

        with patch("clarity.core.llm_client.time.sleep"):
            result = llm_client.invoke("test prompt")

        assert result == "retry success"
        assert llm_client.client.invoke_model.call_count == 2

    def test_transient_errors_constant(self):
        assert "ThrottlingException" in TRANSIENT_ERRORS
        assert "ServiceUnavailableException" in TRANSIENT_ERRORS
        assert "RequestTimeout" in TRANSIENT_ERRORS

    @pytest.mark.asyncio
    async def test_ainvoke(self, llm_client):
        # `ainvoke` simply uses asyncio.to_thread over `invoke`
        import json
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "results": [{"outputText": "async output"}]
        }).encode("utf-8")
        
        llm_client.client.invoke_model.return_value = mock_response
        
        result = await llm_client.ainvoke("async test")
        assert result == "async output"
