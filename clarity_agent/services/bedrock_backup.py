import boto3
import json
from ..config.settings import settings
from ..utils.logging import logger

class BedrockClient:
    def __init__(self):
        """Initializes the Boto3 client for Amazon Bedrock."""
        try:
            # Using the SSO profile we configured
            session = boto3.Session(profile_name=settings.aws_profile_name, region_name=settings.aws_region_name)
            self.client = session.client(service_name='bedrock-runtime')
            logger.info("Bedrock client initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Bedrock client", error=str(e))
            self.client = None

    def invoke(self, prompt: str) -> str:
        """Invokes the specified Bedrock model with a given prompt."""
        if not self.client:
            return "Error: Bedrock client not initialized."

        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}]
            })

            response = self.client.invoke_model(
                body=body, 
                modelId=settings.bedrock_model_id
            )
            
            response_body = json.loads(response.get('body').read())
            completion = response_body.get('content')[0].get('text')
            logger.info("Successfully invoked Bedrock model.", model_id=settings.bedrock_model_id)
            return completion

        except Exception as e:
            logger.error("Error invoking Bedrock model", error=str(e))
            return f"Error: Failed to get response from Bedrock. Details: {e}"

# Create a single instance to be used across the application
bedrock_client = BedrockClient()