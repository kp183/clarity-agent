"""AWS configuration and credentials management for Clarity Agent."""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dataclasses import dataclass
from typing import Optional, Dict, Any
import structlog
import json

logger = structlog.get_logger()

@dataclass
class AWSConfig:
    """AWS configuration settings for Clarity Agent."""
    profile_name: str = "AdministratorAccess-158667298965"
    region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    max_tokens: int = 4000
    temperature: float = 0.1
    top_p: float = 0.9
    
    # Cost management
    max_daily_cost_usd: float = 100.0
    cost_alert_threshold: float = 0.8  # Alert at 80% of daily budget
    
    # Performance settings
    request_timeout: int = 30
    max_retries: int = 3
    retry_backoff_factor: float = 2.0

class AWSCredentialsManager:
    """Manages AWS credentials and session creation."""
    
    def __init__(self, config: AWSConfig):
        self.config = config
        self._session: Optional[boto3.Session] = None
        self._validate_credentials()
    
    def _validate_credentials(self) -> None:
        """Validate AWS credentials and profile configuration."""
        try:
            session = boto3.Session(profile_name=self.config.profile_name)
            # Test credentials by making a simple call
            sts = session.client('sts', region_name=self.config.region)
            identity = sts.get_caller_identity()
            
            logger.info(
                "AWS credentials validated successfully",
                profile=self.config.profile_name,
                account_id=identity.get('Account'),
                user_arn=identity.get('Arn')
            )
            
        except NoCredentialsError:
            logger.error(
                "AWS credentials not found",
                profile=self.config.profile_name,
                suggestion="Run 'aws configure --profile AdministratorAccess-158667298965' to set up credentials"
            )
            raise
        except ClientError as e:
            logger.error(
                "AWS credentials validation failed",
                profile=self.config.profile_name,
                error=str(e)
            )
            raise
    
    @property
    def session(self) -> boto3.Session:
        """Get or create AWS session."""
        if self._session is None:
            self._session = boto3.Session(profile_name=self.config.profile_name)
        return self._session
    
    def get_bedrock_client(self):
        """Get Amazon Bedrock runtime client."""
        return self.session.client(
            'bedrock-runtime',
            region_name=self.config.region
        )
    
    def get_cloudwatch_logs_client(self):
        """Get CloudWatch Logs client."""
        return self.session.client(
            'logs',
            region_name=self.config.region
        )
    
    def get_s3_client(self):
        """Get S3 client for log storage."""
        return self.session.client(
            's3',
            region_name=self.config.region
        )
    
    def get_cost_explorer_client(self):
        """Get Cost Explorer client for usage monitoring."""
        return self.session.client(
            'ce',
            region_name='us-east-1'  # Cost Explorer is only available in us-east-1
        )

class BedrockClient:
    """Amazon Bedrock client with error handling and cost monitoring."""
    
    def __init__(self, credentials_manager: AWSCredentialsManager):
        self.config = credentials_manager.config
        self.client = credentials_manager.get_bedrock_client()
        self.cost_tracker = CostTracker(credentials_manager)
        
    async def invoke_model(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> Dict[str, Any]:
        """Invoke Claude-3 Sonnet model with the given prompt."""
        
        # Check cost limits before making request
        if not await self.cost_tracker.can_make_request():
            raise CostLimitExceededError("Daily cost limit exceeded")
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature,
            "top_p": top_p or self.config.top_p,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            logger.info(
                "Invoking Bedrock model",
                model_id=self.config.bedrock_model_id,
                prompt_length=len(prompt),
                max_tokens=request_body["max_tokens"]
            )
            
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            
            # Track usage for cost monitoring
            await self.cost_tracker.track_usage(
                input_tokens=response_body.get('usage', {}).get('input_tokens', 0),
                output_tokens=response_body.get('usage', {}).get('output_tokens', 0)
            )
            
            logger.info(
                "Bedrock model invocation successful",
                input_tokens=response_body.get('usage', {}).get('input_tokens'),
                output_tokens=response_body.get('usage', {}).get('output_tokens')
            )
            
            return response_body
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ThrottlingException':
                logger.warning("Bedrock API throttling detected, implementing backoff")
                raise BedrockThrottlingError("API rate limit exceeded")
            elif error_code == 'ValidationException':
                logger.error("Invalid request to Bedrock API", error=str(e))
                raise BedrockValidationError(f"Invalid request: {str(e)}")
            else:
                logger.error("Bedrock API error", error_code=error_code, error=str(e))
                raise BedrockAPIError(f"Bedrock API error: {str(e)}")

class CostTracker:
    """Tracks and monitors AWS Bedrock usage costs."""
    
    def __init__(self, credentials_manager: AWSCredentialsManager):
        self.config = credentials_manager.config
        self.ce_client = credentials_manager.get_cost_explorer_client()
        self.daily_usage = 0.0
        
        # Claude-3 Sonnet pricing (as of 2024)
        self.input_token_cost = 0.003 / 1000  # $0.003 per 1K input tokens
        self.output_token_cost = 0.015 / 1000  # $0.015 per 1K output tokens
    
    async def can_make_request(self) -> bool:
        """Check if we can make another request within cost limits."""
        current_cost = await self.get_daily_cost()
        return current_cost < self.config.max_daily_cost_usd
    
    async def track_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Track token usage and calculate costs."""
        input_cost = input_tokens * self.input_token_cost
        output_cost = output_tokens * self.output_token_cost
        total_cost = input_cost + output_cost
        
        self.daily_usage += total_cost
        
        logger.info(
            "Bedrock usage tracked",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            daily_usage=self.daily_usage
        )
        
        # Alert if approaching cost limit
        if self.daily_usage > (self.config.max_daily_cost_usd * self.config.cost_alert_threshold):
            logger.warning(
                "Approaching daily cost limit",
                current_usage=self.daily_usage,
                limit=self.config.max_daily_cost_usd,
                threshold=self.config.cost_alert_threshold
            )
    
    async def get_daily_cost(self) -> float:
        """Get current daily cost from AWS Cost Explorer."""
        # This would implement actual cost retrieval from AWS Cost Explorer
        # For now, return tracked usage
        return self.daily_usage

# Custom exceptions
class BedrockError(Exception):
    """Base exception for Bedrock-related errors."""
    pass

class BedrockThrottlingError(BedrockError):
    """Raised when Bedrock API rate limits are exceeded."""
    pass

class BedrockValidationError(BedrockError):
    """Raised when Bedrock API request validation fails."""
    pass

class BedrockAPIError(BedrockError):
    """Raised for general Bedrock API errors."""
    pass

class CostLimitExceededError(BedrockError):
    """Raised when daily cost limits are exceeded."""
    pass