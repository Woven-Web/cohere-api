"""
Module for interacting with Google's Gemini API to extract event information from preprocessed content.
"""

import logging
from typing import Optional, Dict, Any
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class APIKeyError(LLMError):
    """Raised when there are issues with the API key."""
    pass

class ContentFilterError(LLMError):
    """Raised when content is filtered by the API."""
    pass

class ResponseParsingError(LLMError):
    """Raised when the API response cannot be parsed."""
    pass

EVENT_EXTRACTION_PROMPT = """
Extract event information from the following content. Format the response as JSON with these fields:
{{
    "title": "Event title (or null if not found)",
    "description": "Event description (or null if not found)",
    "start_datetime": "Start time in ISO 8601 format (or null if not found)",
    "end_datetime": "End time in ISO 8601 format (or null if not found)",
    "location": "Event location (or null if not found)"
}}

If a field's information is not found, use null. Ensure datetime strings are in ISO 8601 format (YYYY-MM-DDTHH:MM:SS±HH:MM).

Content to analyze:
{content}

{custom_instructions}
"""

def init_gemini(api_key: str) -> None:
    """
    Initialize the Gemini API client with the provided API key.
    
    Args:
        api_key: The Gemini API key to use for authentication.
        
    Raises:
        APIKeyError: If the API key is invalid or there are authentication issues.
    """
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini API: {str(e)}")
        raise APIKeyError(f"Failed to initialize Gemini API: {str(e)}")

def create_extraction_prompt(content: str, custom_instructions: Optional[str] = None) -> str:
    """
    Create the prompt for event information extraction.
    
    Args:
        content: The preprocessed content to analyze.
        custom_instructions: Optional additional instructions for the model.
        
    Returns:
        str: The formatted prompt for the model.
    """
    instructions = custom_instructions if custom_instructions else "Extract all available event information."
    return EVENT_EXTRACTION_PROMPT.format(content=content, custom_instructions=instructions)

@retry(
    retry=retry_if_exception_type(LLMError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry_error_callback=lambda retry_state: retry_state.outcome.result()
)
async def extract_event_info(
    content: str,
    api_key: str,
    custom_instructions: Optional[str] = None,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    Extract event information from the provided content using the Gemini API.
    
    Args:
        content: The preprocessed content to analyze.
        api_key: The Gemini API key to use.
        custom_instructions: Optional additional instructions for the model.
        temperature: The temperature parameter for generation (default: 0.1).
        
    Returns:
        Dict[str, Any]: The extracted event information.
        
    Raises:
        APIKeyError: If there are issues with the API key.
        ContentFilterError: If content is filtered by the API.
        ResponseParsingError: If the response cannot be parsed.
        LLMError: For other LLM-related errors.
    """
    try:
        # Initialize the API client
        init_gemini(api_key)
        
        # Create the model instance with specific configuration
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            generation_config=GenerationConfig(
                temperature=temperature,
                top_p=1,
                top_k=1,
                max_output_tokens=2048
            )
        )
        
        # Create the prompt
        prompt = create_extraction_prompt(content, custom_instructions)
        
        # Generate response
        logger.debug("Sending request to Gemini API")
        response = await model.generate_content_async(prompt)
        
        # Log the raw response for debugging
        logger.debug(f"Raw response from Gemini API: {response.text}")
        
        if not response.text or not response.text.strip():
            raise ResponseParsingError("Empty response from Gemini API")
            
        # Log response for debugging (excluding sensitive information)
        logger.debug("Received response from Gemini API")
        
        # Parse the response
        try:
            # The response should be in JSON format as requested in the prompt
            import json
            # Try to clean up the response text by finding JSON-like content
            text = response.text.strip()
            if text.startswith('```json'):
                text = text[7:]  # Remove ```json prefix
            if text.endswith('```'):
                text = text[:-3]  # Remove ``` suffix
            text = text.strip()
            
            result = json.loads(text)
            
            # Validate required fields
            required_fields = ["title", "description", "start_datetime", "end_datetime", "location"]
            for field in required_fields:
                if field not in result:
                    result[field] = None
                    
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini API response as JSON: {str(e)}")
            raise ResponseParsingError(f"Failed to parse response as JSON: {str(e)}")
            
    except Exception as e:
        if "blocked" in str(e).lower():
            logger.error(f"Content filtered by Gemini API: {str(e)}")
            raise ContentFilterError(f"Content filtered by Gemini API: {str(e)}")
        logger.error(f"Error during event extraction: {str(e)}")
        if isinstance(e, (APIKeyError, ContentFilterError, ResponseParsingError)):
            raise
        raise LLMError(f"Error during event extraction: {str(e)}") 