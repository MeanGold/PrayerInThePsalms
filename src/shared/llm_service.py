"""
LLM service wrapper for Amazon Bedrock.

This module provides a wrapper for generating personalized psalm recommendations
using Amazon Bedrock's LLM models. It includes prompt templating, error handling,
retry logic with exponential backoff, and metrics tracking for monitoring.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 8.3, 8.4, 10.4**
"""

import json
import time
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .config import config
from .logging_config import get_logger, log_metric, log_error
from .metrics import emit_llm_metric


logger = get_logger("llm_service")


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMGenerationFailedError(LLMServiceError):
    """
    Exception raised when the LLM fails to generate a response.
    
    **Validates: Requirement 8.3**
    """
    pass


class PsalmRecommendation:
    """
    Data class representing a psalm recommendation response.
    
    Attributes:
        psalm_numbers: List of recommended psalm numbers.
        verses: Key verses from the recommended psalms.
        guidance: Personalized contextual guidance.
        raw_response: The raw LLM response text.
    """
    
    def __init__(
        self,
        psalm_numbers: List[int],
        verses: List[str],
        guidance: str,
        raw_response: str
    ):
        self.psalm_numbers = psalm_numbers
        self.verses = verses
        self.guidance = guidance
        self.raw_response = raw_response
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "psalm_numbers": self.psalm_numbers,
            "verses": self.verses,
            "guidance": self.guidance
        }


class LLMService:
    """
    Service for generating personalized psalm recommendations using Amazon Bedrock LLM.
    
    This class provides methods to generate empathetic and supportive psalm recommendations
    with automatic retry logic, error handling, and metrics tracking.
    
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 8.3, 8.4, 10.4**
    """
    
    def __init__(
        self,
        bedrock_client: Optional[Any] = None,
        model_id: Optional[str] = None,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Initialize the LLM service.
        
        Args:
            bedrock_client: Optional boto3 Bedrock Runtime client. If not provided,
                          a new client will be created.
            model_id: Optional LLM model ID. Defaults to config value.
            max_retries: Optional maximum retry attempts. Defaults to config value.
            backoff_base: Optional exponential backoff base. Defaults to config value.
            temperature: Optional temperature for generation. Defaults to 0.7.
            max_tokens: Optional maximum tokens to generate. Defaults to 1000.
        """
        self.bedrock_client = bedrock_client or self._create_bedrock_client()
        self.model_id = model_id or config.LLM_MODEL_ID
        self.max_retries = max_retries if max_retries is not None else config.MAX_RETRIES
        self.backoff_base = backoff_base if backoff_base is not None else config.RETRY_BACKOFF_BASE
        self.temperature = temperature if temperature is not None else 0.7
        self.max_tokens = max_tokens if max_tokens is not None else 1000
        
        logger.info(
            "LLMService initialized",
            extra={
                "model_id": self.model_id,
                "max_retries": self.max_retries,
                "temperature": self.temperature
            }
        )
    
    def _create_bedrock_client(self) -> Any:
        """
        Create a boto3 Bedrock Runtime client with configured settings.
        
        Returns:
            Configured boto3 Bedrock Runtime client.
        """
        return boto3.client(
            "bedrock-runtime",
            region_name=config.BEDROCK_REGION
        )
    
    def generate_recommendation(
        self,
        emotional_input: str,
        retrieved_psalms: List[Dict[str, Any]],
        request_id: Optional[str] = None
    ) -> PsalmRecommendation:
        """
        Generate a personalized psalm recommendation based on user's emotional input.
        
        This method creates a prompt that includes the user's emotional state and
        retrieved psalm context, then invokes the LLM to generate an empathetic
        and supportive response.
        
        **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 8.3, 10.4**
        
        Args:
            emotional_input: The user's 1-2 sentence description of their emotional state.
            retrieved_psalms: List of semantically similar psalms with metadata.
            request_id: Optional request ID for tracking and logging.
            
        Returns:
            PsalmRecommendation object containing psalm numbers, verses, and guidance.
            
        Raises:
            LLMGenerationFailedError: When the LLM fails to generate a response.
            LLMServiceError: For other LLM generation errors.
        """
        if not emotional_input or not emotional_input.strip():
            raise ValueError("Emotional input cannot be empty")
        
        if not retrieved_psalms:
            raise ValueError("Retrieved psalms list cannot be empty")
        
        start_time = time.time()
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                # Build the prompt with emotional input and psalm context (Requirements 4.1, 4.4)
                prompt = self._build_prompt(emotional_input, retrieved_psalms)
                
                # Prepare the request body based on the model
                request_body = self._prepare_request_body(prompt)
                
                # Invoke the Bedrock LLM
                response = self.bedrock_client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body),
                    contentType="application/json",
                    accept="application/json"
                )
                
                # Parse the response
                response_body = json.loads(response["body"].read())
                recommendation_text = self._extract_text(response_body)
                
                # Parse the recommendation to extract structured data (Requirement 4.2)
                recommendation = self._parse_recommendation(recommendation_text)
                
                # Track success metrics (Requirement 10.4)
                duration_ms = (time.time() - start_time) * 1000
                log_metric(
                    metric_name="llm_invocation_success",
                    value=1,
                    unit="count",
                    metadata={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "attempt": attempt + 1,
                        "psalm_count": len(recommendation.psalm_numbers)
                    }
                )
                
                # Emit CloudWatch metrics (Requirement 10.4)
                emit_llm_metric(
                    success=True,
                    duration_ms=duration_ms,
                    request_id=request_id
                )
                
                logger.info(
                    "LLM recommendation generated successfully",
                    extra={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "psalm_count": len(recommendation.psalm_numbers),
                        "attempt": attempt + 1
                    }
                )
                
                return recommendation
                
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                last_error = e
                
                # Check if this is a retryable error
                if self._is_retryable_error(error_code):
                    attempt += 1
                    if attempt < self.max_retries:
                        # Calculate exponential backoff delay
                        delay = self.backoff_base ** attempt
                        logger.warning(
                            f"Retryable error occurred, retrying in {delay}s",
                            extra={
                                "request_id": request_id,
                                "error_code": error_code,
                                "attempt": attempt,
                                "delay_seconds": delay
                            }
                        )
                        time.sleep(delay)
                        continue
                
                # Non-retryable error or max retries reached
                break
                
            except (BotoCoreError, json.JSONDecodeError, KeyError, ValueError) as e:
                last_error = e
                attempt += 1
                if attempt < self.max_retries:
                    delay = self.backoff_base ** attempt
                    logger.warning(
                        f"Transient error occurred, retrying in {delay}s",
                        extra={
                            "request_id": request_id,
                            "error_type": type(e).__name__,
                            "attempt": attempt,
                            "delay_seconds": delay
                        }
                    )
                    time.sleep(delay)
                    continue
                break
        
        # All retries exhausted or non-retryable error
        self._handle_failure(last_error, request_id, start_time)
    
    def _build_prompt(
        self,
        emotional_input: str,
        retrieved_psalms: List[Dict[str, Any]]
    ) -> str:
        """
        Build the LLM prompt with emotional input and psalm context.
        
        The prompt is designed to elicit an empathetic and supportive response
        that includes psalm numbers, key verses, and contextual guidance.
        
        **Validates: Requirements 4.1, 4.3, 4.4**
        
        Args:
            emotional_input: The user's emotional state description.
            retrieved_psalms: List of semantically similar psalms with metadata.
            
        Returns:
            The formatted prompt string.
        """
        # Format the psalm context
        psalm_context = self._format_psalm_context(retrieved_psalms)
        
        # Build the prompt with empathetic tone (Requirement 4.3)
        prompt = f"""You are a compassionate spiritual guide helping someone find comfort and guidance in the Psalms.

A person has shared their feelings with you:
"{emotional_input}"

Based on their emotional state, here are some relevant psalms that may provide comfort and guidance:

{psalm_context}

Please provide a warm, empathetic response that:
1. Acknowledges their feelings with compassion
2. Recommends 2-3 specific psalms from the list above that best match their emotional state
3. Includes 1-2 key verses from the recommended psalms (with verse numbers)
4. Offers brief, supportive guidance on how these psalms might speak to their situation

Format your response as follows:
PSALMS: [list psalm numbers separated by commas]
VERSES: [list key verses with psalm and verse numbers]
GUIDANCE: [your empathetic message and guidance]

Remember to be warm, supportive, and respectful of their emotional state."""

        return prompt
    
    def _format_psalm_context(self, retrieved_psalms: List[Dict[str, Any]]) -> str:
        """
        Format the retrieved psalms into a readable context string.
        
        Args:
            retrieved_psalms: List of psalm dictionaries with metadata.
            
        Returns:
            Formatted string with psalm information.
        """
        context_parts = []
        
        for i, psalm in enumerate(retrieved_psalms, 1):
            psalm_num = psalm.get("psalm_number", "Unknown")
            themes = psalm.get("themes", [])
            emotional_context = psalm.get("emotional_context", "")
            key_verses = psalm.get("key_verses", [])
            
            context = f"Psalm {psalm_num}:"
            
            if themes:
                context += f"\n  Themes: {', '.join(themes)}"
            
            if emotional_context:
                context += f"\n  Emotional Context: {emotional_context}"
            
            if key_verses:
                context += f"\n  Key Verses: {', '.join(key_verses[:2])}"  # Limit to 2 verses
            
            context_parts.append(context)
        
        return "\n\n".join(context_parts)
    
    def _prepare_request_body(self, prompt: str) -> Dict[str, Any]:
        """
        Prepare the request body for the LLM model.
        
        Different Bedrock LLM models have different input formats.
        This method handles the format for Claude models.
        
        Args:
            prompt: The formatted prompt text.
            
        Returns:
            Dictionary containing the request body.
        """
        # Claude 3 format (Messages API)
        if "claude-3" in self.model_id:
            return {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
        
        # Claude 2 format (Text Completions API)
        elif "claude" in self.model_id:
            return {
                "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                "max_tokens_to_sample": self.max_tokens,
                "temperature": self.temperature,
                "stop_sequences": ["\n\nHuman:"]
            }
        
        # Default format (Claude 3)
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
    
    def _extract_text(self, response_body: Dict[str, Any]) -> str:
        """
        Extract the generated text from the model response.
        
        Args:
            response_body: The parsed JSON response from the model.
            
        Returns:
            The generated text string.
            
        Raises:
            KeyError: If the expected text field is not found.
        """
        # Claude 3 format (Messages API)
        if "content" in response_body:
            content = response_body["content"]
            if isinstance(content, list) and len(content) > 0:
                return content[0].get("text", "")
            return str(content)
        
        # Claude 2 format (Text Completions API)
        elif "completion" in response_body:
            return response_body["completion"]
        
        # Fallback
        raise KeyError(f"Could not find text in response: {response_body.keys()}")
    
    def _parse_recommendation(self, text: str) -> PsalmRecommendation:
        """
        Parse the LLM response to extract structured recommendation data.
        
        **Validates: Requirement 4.2**
        
        Args:
            text: The raw LLM response text.
            
        Returns:
            PsalmRecommendation object with parsed data.
            
        Raises:
            ValueError: If the response cannot be parsed.
        """
        psalm_numbers = []
        verses = []
        guidance = ""
        
        lines = text.strip().split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("PSALMS:"):
                current_section = "psalms"
                # Extract psalm numbers
                psalm_text = line.replace("PSALMS:", "").strip()
                psalm_numbers = self._extract_psalm_numbers(psalm_text)
            
            elif line.startswith("VERSES:"):
                current_section = "verses"
                verse_text = line.replace("VERSES:", "").strip()
                if verse_text:
                    verses.append(verse_text)
            
            elif line.startswith("GUIDANCE:"):
                current_section = "guidance"
                guidance_text = line.replace("GUIDANCE:", "").strip()
                if guidance_text:
                    guidance = guidance_text
            
            elif current_section == "verses" and line:
                verses.append(line)
            
            elif current_section == "guidance" and line:
                if guidance:
                    guidance += " " + line
                else:
                    guidance = line
        
        # Validate that we extracted the required components
        if not psalm_numbers:
            raise ValueError("Could not extract psalm numbers from LLM response")
        
        if not guidance:
            raise ValueError("Could not extract guidance from LLM response")
        
        return PsalmRecommendation(
            psalm_numbers=psalm_numbers,
            verses=verses,
            guidance=guidance.strip(),
            raw_response=text
        )
    
    def _extract_psalm_numbers(self, text: str) -> List[int]:
        """
        Extract psalm numbers from text.
        
        Args:
            text: Text containing psalm numbers (e.g., "23, 46, 91").
            
        Returns:
            List of psalm numbers as integers.
        """
        import re
        
        # Find all numbers in the text
        numbers = re.findall(r'\d+', text)
        
        # Convert to integers and filter valid psalm numbers (1-150)
        psalm_numbers = [int(n) for n in numbers if 1 <= int(n) <= 150]
        
        return psalm_numbers
    
    def _is_retryable_error(self, error_code: str) -> bool:
        """
        Determine if an error code indicates a retryable failure.
        
        Args:
            error_code: The AWS error code from the exception.
            
        Returns:
            True if the error is retryable, False otherwise.
        """
        retryable_codes = {
            "ThrottlingException",
            "ServiceUnavailableException",
            "InternalServerException",
            "TooManyRequestsException",
            "ModelTimeoutException"
        }
        return error_code in retryable_codes
    
    def _handle_failure(
        self,
        error: Exception,
        request_id: Optional[str],
        start_time: float
    ) -> None:
        """
        Handle LLM generation failure by logging and raising appropriate exception.
        
        **Validates: Requirements 8.3, 8.4, 10.4**
        
        Args:
            error: The exception that caused the failure.
            request_id: Optional request ID for tracking.
            start_time: The time when the request started.
            
        Raises:
            LLMGenerationFailedError: When the LLM fails to generate a response.
            LLMServiceError: For other errors.
        """
        duration_ms = (time.time() - start_time) * 1000
        
        # Track failure metrics (Requirement 10.4)
        log_metric(
            metric_name="llm_invocation_failed",
            value=1,
            unit="count",
            metadata={
                "request_id": request_id,
                "duration_ms": duration_ms,
                "error_type": type(error).__name__
            }
        )
        
        # Emit CloudWatch metrics (Requirement 10.4)
        emit_llm_metric(
            success=False,
            duration_ms=duration_ms,
            request_id=request_id
        )
        
        # Log error with context (Requirement 8.4)
        log_error(
            request_id=request_id or "unknown",
            error=error,
            context={
                "service": "llm_service",
                "model_id": self.model_id,
                "duration_ms": duration_ms
            }
        )
        
        # Raise appropriate exception (Requirement 8.3)
        error_message = f"Failed to generate LLM recommendation: {str(error)}"
        raise LLMGenerationFailedError(error_message) from error
    
    def generate_fallback_response(
        self,
        retrieved_psalms: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a fallback response when LLM fails.
        
        Returns psalm references without personalized text as specified
        in Requirement 8.3.
        
        **Validates: Requirement 8.3**
        
        Args:
            retrieved_psalms: List of semantically similar psalms with metadata.
            
        Returns:
            Dictionary with psalm references and basic information.
        """
        fallback_psalms = []
        
        for psalm in retrieved_psalms[:3]:  # Limit to top 3
            psalm_info = {
                "psalm_number": psalm.get("psalm_number"),
                "themes": psalm.get("themes", []),
                "key_verses": psalm.get("key_verses", [])
            }
            fallback_psalms.append(psalm_info)
        
        return {
            "psalms": fallback_psalms,
            "message": "Here are some psalms that may provide comfort. We were unable to generate personalized guidance at this time."
        }
