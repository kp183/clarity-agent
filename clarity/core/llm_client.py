"""LLM client for Clarity — supports AWS Bedrock and Groq."""

import boto3
import json
import asyncio
import time
from typing import Optional
from botocore.exceptions import ClientError

from ..config import settings
from .  import logger

TRANSIENT_ERRORS = {"ThrottlingException", "ServiceUnavailableException", "RequestTimeout"}


class LLMClient:
    """
    Multi-provider LLM wrapper supporting AWS Bedrock and Groq.
    Provider is selected via settings.llm_provider ('bedrock' or 'groq').
    """

    def __init__(self):
        self.client: Optional[boto3.client] = None
        self._groq_client = None

        if settings.llm_provider == "groq":
            self._init_groq()
        else:
            self._init_bedrock()

    def _init_bedrock(self):
        try:
            session = boto3.Session(
                profile_name=settings.aws_profile_name,
                region_name=settings.aws_region_name,
            )
            self.client = session.client(service_name="bedrock-runtime")
            logger.info("✅ Bedrock client initialized.", model=settings.bedrock_model_id)
        except Exception as e:
            logger.error("❌ Failed to initialize Bedrock client", error=str(e))

    def _init_groq(self):
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=settings.groq_api_key)
            logger.info("✅ Groq client initialized.", model=settings.groq_model_id)
        except Exception as e:
            logger.error("❌ Failed to initialize Groq client", error=str(e))

    def invoke(self, prompt: str, max_retries: int = 3) -> str:
        """Invoke the configured LLM provider with retry logic."""
        if settings.llm_provider == "groq":
            return self._invoke_groq(prompt)
        return self._invoke_bedrock(prompt, max_retries)

    def _invoke_groq(self, prompt: str) -> str:
        """Invoke Groq API."""
        if not self._groq_client:
            return "Error: Groq client not initialized. Check GROQ_API_KEY."
        try:
            response = self._groq_client.chat.completions.create(
                model=settings.groq_model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=settings.temperature,
            )
            text = response.choices[0].message.content or ""
            cleaned = self._extract_json_block(text)
            logger.info("✅ Groq invocation successful.", model=settings.groq_model_id,
                        preview=cleaned[:100] + "..." if len(cleaned) > 100 else cleaned)
            return cleaned
        except Exception as e:
            logger.error("Groq invocation failed", error=str(e))
            return f"Error: {e}"

    def _invoke_bedrock(self, prompt: str, max_retries: int = 3) -> str:
        """Invoke AWS Bedrock with exponential backoff retry."""
        if not self.client:
            return "Error: Bedrock client not initialized. Check AWS configuration."

        for attempt in range(max_retries):
            try:
                return self._invoke_once(prompt)
            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code in TRANSIENT_ERRORS and attempt < max_retries - 1:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Bedrock transient error, retry {attempt + 1}", code=code)
                    time.sleep(sleep_time)
                else:
                    logger.error("Bedrock invocation failed", error=str(e))
                    return f"Error: {e}"
        return "Error: Max retries exceeded"

    def _invoke_once(self, prompt: str) -> str:
        """Single Bedrock invocation — no retry logic."""
        body = self._build_request_body(prompt)

        response = self.client.invoke_model(
            body=json.dumps(body),
            modelId=settings.bedrock_model_id,
            accept="application/json",
            contentType="application/json",
        )

        response_body = json.loads(response["body"].read())
        output_text = self._extract_output(response_body)
        cleaned = self._extract_json_block(output_text)

        logger.info(
            "✅ Bedrock invocation successful.",
            model=settings.bedrock_model_id,
            preview=cleaned[:100] + "..." if len(cleaned) > 100 else cleaned,
        )
        return cleaned

    async def ainvoke(self, prompt: str) -> str:
        """Async wrapper — runs the sync invoke in a thread pool."""
        return await asyncio.to_thread(self.invoke, prompt)

    def _build_request_body(self, prompt: str) -> dict:
        """Build model-specific request body."""
        if "anthropic" in settings.bedrock_model_id:
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": settings.max_tokens,
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "messages": [{"role": "user", "content": prompt}],
            }
        elif "amazon.nova" in settings.bedrock_model_id:
            # Amazon Nova models use the Converse-style messages API
            return {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "maxTokens": settings.max_tokens,
                    "temperature": settings.temperature,
                    "topP": settings.top_p,
                },
            }
        elif "amazon.titan" in settings.bedrock_model_id:
            return {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": settings.max_tokens,
                    "temperature": settings.temperature,
                    "topP": settings.top_p,
                },
            }
        else:
            raise ValueError(f"Unsupported model: {settings.bedrock_model_id}")

    def _extract_output(self, response_body: dict) -> str:
        """Extract text from model-specific response structure."""
        if "anthropic" in settings.bedrock_model_id:
            return response_body.get("content", [{}])[0].get("text", "").strip()
        elif "amazon.nova" in settings.bedrock_model_id:
            # Nova response: {"output": {"message": {"content": [{"text": "..."}]}}}
            try:
                return response_body["output"]["message"]["content"][0]["text"].strip()
            except (KeyError, IndexError):
                return str(response_body)
        else:
            # Titan
            return response_body.get("results", [{}])[0].get("outputText", "").strip()

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """Extract the first valid JSON object from AI output."""
        if not text:
            return "{}"
        if text.startswith("{") and text.endswith("}"):
            return text

        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            candidate = text[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                return candidate.replace("\n", " ").replace("\r", " ")

        return text


# Shared singleton
llm_client = LLMClient()
