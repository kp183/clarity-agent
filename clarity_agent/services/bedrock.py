import boto3
import json
from typing import Optional

# Import the application settings and logger
from ..config.settings import settings
from ..utils.logging import logger

class BedrockClient:
    """
    A wrapper for the Amazon Bedrock runtime client that supports multiple
    foundation models (Anthropic Claude and Amazon Titan).
    """

    def __init__(self):
        """
        Initializes a Boto3 Bedrock runtime client using the AWS profile and region
        specified in the application settings.
        """
        self.client: Optional[boto3.client] = None
        try:
            # Create a session using the SSO profile configured via `aws configure sso`
            session = boto3.Session(
                profile_name=settings.aws_profile_name,
                region_name=settings.aws_region_name
            )
            self.client = session.client(service_name="bedrock-runtime")
            logger.info("✅ Bedrock client initialized successfully.")
        except Exception as e:
            logger.error("❌ Failed to initialize Bedrock client", error=str(e))
            # The client remains None, and subsequent calls will fail gracefully

    def invoke(self, prompt: str) -> str:
        """
        Invokes the configured Bedrock model with a given prompt, handles the
        specific request/response format for the model provider, and returns
        a clean, extracted text or JSON string.
        """
        if not self.client:
            return "Error: Bedrock client not initialized. Check AWS configuration."

        try:
            # --- Build the request body based on the model provider ---
            if "anthropic" in settings.bedrock_model_id:
                # Format for Anthropic Claude models
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": settings.max_tokens,
                    "temperature": settings.temperature,
                    "top_p": settings.top_p,
                    "messages": [{"role": "user", "content": prompt}],
                })
            elif "amazon.titan" in settings.bedrock_model_id:
                # Format for Amazon Titan Text models
                body = json.dumps({
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": settings.max_tokens,
                        "temperature": settings.temperature,
                        "topP": settings.top_p,
                    },
                })
            else:
                raise ValueError(f"Unsupported model provider for model ID: {settings.bedrock_model_id}")

            # --- Invoke the Bedrock model ---
            response = self.client.invoke_model(
                body=body,
                modelId=settings.bedrock_model_id,
                accept="application/json",
                contentType="application/json",
            )

            # --- Parse the response based on the model provider ---
            response_body = json.loads(response.get("body").read())

            if "anthropic" in settings.bedrock_model_id:
                # Anthropic models nest the content in a list
                output_text = response_body.get("content", [{}])[0].get("text", "").strip()
            else:  # Assumes Amazon Titan
                # Titan models have a different structure
                output_text = response_body.get("results", [{}])[0].get("outputText", "").strip()
            
            # --- Clean the final output ---
            cleaned_output = self._extract_json_block(output_text)

            logger.info(
                "✅ Bedrock model invocation successful.",
                model_id=settings.bedrock_model_id,
                preview=cleaned_output[:100] + "..." if len(cleaned_output) > 100 else cleaned_output
            )
            return cleaned_output

        except Exception as e:
            logger.error("❌ Error invoking Bedrock model", error=str(e))
            return f"Error: Failed to get response from Bedrock. Details: {e}"

    @staticmethod
    def _extract_json_block(text: str) -> str:
        """
        Extracts the first valid JSON object from a string that might contain
        surrounding conversational text from the LLM.
        """
        if not text:
            return "{}"

        # Check 1: The text is already a perfect JSON object.
        if text.startswith("{") and text.endswith("}"):
            return text

        # Check 2: Find the first '{' and last '}' to extract a JSON block.
        start_index = text.find("{")
        end_index = text.rfind("}")

        if 0 <= start_index < end_index:
            candidate = text[start_index : end_index + 1]
            try:
                # If it's valid JSON, we're done.
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                # If it's almost JSON but has newlines, try cleaning it.
                cleaned_candidate = candidate.replace("\n", " ").replace("\r", " ")
                return cleaned_candidate

        # Fallback: If no JSON is found, return the original text.
        return text

# A single, shared instance for the entire application to use
bedrock_client = BedrockClient()