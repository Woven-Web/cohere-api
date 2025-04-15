"""
Module for interacting with Google's Gemini API to extract event information from preprocessed content.
"""

import logging
from typing import Optional, Dict, Any
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time
import re
import json

logger = logging.getLogger(__name__)

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    def __init__(self, 
                 message: str,
                 details: Optional[Dict[str, Any]] = None,
                 original_error: Optional[Exception] = None):
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        self.timestamp = time.time()
        
        # Log detailed error information
        logger.error(f"LLM Error occurred at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp))}")
        logger.error(f"Message: {message}")
        if self.details:
            logger.error(f"Details: {json.dumps(self.details, indent=2)}")
        if self.original_error:
            logger.error(f"Original error: {str(self.original_error)}")
            if hasattr(self.original_error, '__traceback__'):
                import traceback
                logger.error("Traceback:\n" + "".join(traceback.format_tb(self.original_error.__traceback__)))
        
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Format error message with relevant context."""
        parts = [self.message]
        
        if self.details:
            relevant_details = {
                k: v for k, v in self.details.items()
                if k in {'model_name', 'temperature', 'response_text', 'error_type', 'attempt_number'}
            }
            if relevant_details:
                parts.append(f"Details: {relevant_details}")
        
        if self.original_error:
            parts.append(f"Original error: {str(self.original_error)}")
            
        return " | ".join(parts)

class APIKeyError(LLMError):
    """Raised when there are issues with the API key."""
    pass

class ContentFilterError(LLMError):
    """Raised when content is filtered by the API."""
    pass

class ResponseParsingError(LLMError):
    """Raised when the API response cannot be parsed."""
    pass

EVENT_EXTRACTION_PROMPT = '''
You are a JSON generator that extracts event information from content. Your response must be ONLY a valid JSON object with no additional text.

Analyze the following content and extract:
1. Event title (from headings or prominent text)
2. Description (preserve ALL text about the event, maintaining original formatting including line breaks, lists, bold/italic markers, etc.)
3. Date and time (start and end times)
4. Location (venue name and/or address)

Return ONLY a JSON object in this exact format:
{
    "title": "string or null",
    "description": "string or null",
    "start_datetime": "ISO 8601 datetime string or null",
    "end_datetime": "ISO 8601 datetime string or null",
    "location": "string or null"
}

Rules:
- Use null for missing information
- Format dates as ISO 8601 (YYYY-MM-DDTHH:MM:SS±HH:MM)
- For dates without times, use 00:00:00
- Preserve ALL original text in description, including:
  * Full paragraphs
  * Line breaks
  * Lists and bullet points
  * Formatting markers (bold, italic, etc.)
  * Links and references
  * Any additional details or notes
- Include both venue name and address in location if available
- Do not truncate or summarize the description

Content to analyze:
{content}

Additional instructions:
{custom_instructions}

Remember: Respond ONLY with the JSON object, no other text.
'''

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
    try:
        instructions = custom_instructions if custom_instructions else "Extract all available event information."
        # Use a safer string formatting approach
        prompt_template = EVENT_EXTRACTION_PROMPT.replace("{content}", "%content%").replace("{custom_instructions}", "%instructions%")
        prompt = prompt_template.replace("%content%", content).replace("%instructions%", instructions)
        logger.debug(f"Created prompt with content length: {len(content)}")
        return prompt
    except Exception as e:
        logger.error(f"Error creating extraction prompt: {str(e)}", exc_info=True)
        raise LLMError(
            f"Failed to create extraction prompt: {str(e)}",
            details={
                'content_length': len(content) if content else 0,
                'has_custom_instructions': custom_instructions is not None,
                'error_type': type(e).__name__
            },
            original_error=e
        )

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
    # Initialize variables at the top level of the function
    prompt = None
    text = None
    
    try:
        # Initialize the API client
        init_gemini(api_key)
        
        # Create the model instance with specific configuration
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-lite",
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=10000,
                candidate_count=1
            )
        )
        
        # Create the prompt
        prompt = create_extraction_prompt(content, custom_instructions)
        logger.debug(f"Generated prompt:\n{prompt}")
        
        # Generate response
        logger.debug("Sending request to Gemini API")
        try:
            response = await model.generate_content_async(prompt)
        except Exception as e:
            error_details = {
                'model_name': 'gemini-2.0-flash-lite',
                'temperature': temperature,
                'error_type': type(e).__name__,
                'prompt': prompt
            }
            if "blocked" in str(e).lower():
                raise ContentFilterError(
                    f"Content filtered by Gemini API: {str(e)}", 
                    details=error_details,
                    original_error=e
                )
            raise LLMError(
                f"Error during API call: {str(e)}", 
                details=error_details,
                original_error=e
            )
        
        # Log the raw response for debugging
        logger.debug(f"Raw response from Gemini API: {response.text}")
        
        if not response.text or not response.text.strip():
            raise ResponseParsingError(
                "Empty response from Gemini API",
                details={
                    'model_name': 'gemini-2.0-flash-lite',
                    'temperature': temperature,
                    'response_text': response.text,
                    'prompt': prompt
                }
            )
            
        # Clean up the response text
        text = response.text.strip()
        logger.debug(f"Initial cleaned text: {text}")
        
        # Remove any markdown code block markers and language specifiers
        text = re.sub(r'^```\w*\n?', '', text)  # Remove opening code block
        text = re.sub(r'\n?```$', '', text)     # Remove closing code block
        text = text.strip()
        logger.debug(f"Text after markdown cleanup: {text}")
        
        # Try to find JSON-like content if the text contains other content
        # Use a simpler regex pattern for JSON matching
        json_match = re.search(r'\{[^}]*"title"[^}]*\}', text, re.DOTALL)
        if json_match:
            text = json_match.group(0)
            logger.debug(f"Found JSON match: {text}")
        else:
            logger.warning("No JSON-like content found in response")
            logger.debug(f"Full response text: {text}")
            # If no JSON found, try to extract key-value pairs
            try:
                # Extract fields using regex
                title_match = re.search(r'"title"["\s:]+([^"\n,}]+)', text)
                desc_match = re.search(r'"description"["\s:]+([^"\n,}]+)', text)
                start_match = re.search(r'"start_datetime"["\s:]+([^"\n,}]+)', text)
                end_match = re.search(r'"end_datetime"["\s:]+([^"\n,}]+)', text)
                loc_match = re.search(r'"location"["\s:]+([^"\n,}]+)', text)
                
                # Construct JSON manually
                text = '{'
                text += f'"title": "{title_match.group(1) if title_match else "null"}",'
                text += f'"description": "{desc_match.group(1) if desc_match else "null"}",'
                text += f'"start_datetime": "{start_match.group(1) if start_match else "null"}",'
                text += f'"end_datetime": "{end_match.group(1) if end_match else "null"}",'
                text += f'"location": "{loc_match.group(1) if loc_match else "null"}"'
                text += '}'
                logger.debug(f"Constructed JSON from regex matches: {text}")
            except Exception as e:
                logger.warning(f"Failed to extract fields using regex: {str(e)}")
                # If all else fails, return null values
                text = '{"title": null, "description": null, "start_datetime": null, "end_datetime": null, "location": null}'
        
        # Parse the JSON
        try:
            # Try to fix common JSON formatting issues
            text = text.replace('\n', '')  # Remove newlines
            text = re.sub(r',\s*}', '}', text)  # Remove trailing commas
            text = re.sub(r',\s*]', ']', text)  # Remove trailing commas in arrays
            logger.debug(f"Text after JSON cleanup: {text}")
            
            # Try to parse the JSON
            try:
                result = json.loads(text)
                logger.debug(f"Successfully parsed JSON: {result}")
                
                # Ensure the result is a dictionary
                if not isinstance(result, dict):
                    # If it's a list with one dictionary, use that
                    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
                        result = result[0]
                        logger.warning("Parsed JSON was a list containing one dictionary. Using the dictionary.")
                    else:
                        raise ResponseParsingError(
                            f"Expected a JSON object, but got type {type(result).__name__}",
                            details={
                                'model_name': 'gemini-2.0-flash-lite',
                                'temperature': temperature,
                                'response_text': text,
                                'parsed_type': type(result).__name__,
                                'prompt': prompt
                            }
                        )
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini API response as JSON: {str(e)}")
                logger.error(f"Response text before parsing: {text}")
                # Directly raise the error if the first parse attempt fails
                raise ResponseParsingError(
                    f"Failed to parse response as JSON: {str(e)}",
                    details={
                        'model_name': 'gemini-2.0-flash-lite',
                        'temperature': temperature,
                        'response_text': text,
                        'error_type': 'JSONDecodeError',
                        'json_error_position': e.pos,
                        'json_error_message': e.msg,
                        'prompt': prompt
                    },
                    original_error=e
                )
            
            # Validate and clean up fields
            required_fields = ["title", "description", "start_datetime", "end_datetime", "location"]
            cleaned_result = {}
            
            for field in required_fields:
                value = result.get(field)
                logger.debug(f"Processing field '{field}' with value: {value}")
                if value is None or value == "null" or value == "":
                    cleaned_result[field] = None
                elif isinstance(value, str):
                    cleaned_value = value.strip()
                    if cleaned_value.lower() in ['none', 'null', 'not found', '']:
                        cleaned_result[field] = None
                    else:
                        cleaned_result[field] = cleaned_value
                else:
                    cleaned_result[field] = value
            
            logger.debug(f"Final cleaned result: {cleaned_result}")
            return cleaned_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini API response as JSON: {str(e)}")
            logger.error(f"Response text: {text}")
            logger.error(f"JSON error position: character {e.pos}")
            logger.error(f"JSON error message: {e.msg}")
            logger.error(f"JSON document: {e.doc}")
            raise ResponseParsingError(
                f"Failed to parse response as JSON: {str(e)}",
                details={
                    'model_name': 'gemini-2.0-flash-lite',
                    'temperature': temperature,
                    'response_text': text,
                    'error_type': 'JSONDecodeError',
                    'json_error_position': e.pos,
                    'json_error_message': e.msg,
                    'prompt': prompt
                },
                original_error=e
            )
            
    except Exception as e:
        if isinstance(e, (APIKeyError, ContentFilterError, ResponseParsingError, LLMError)):
            raise
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"Unexpected error during event extraction: {str(e)}\nTraceback:\n{tb_str}")
        raise LLMError(
            f"Error during event extraction: {str(e)}",
            details={
                'model_name': 'gemini-2.0-flash-lite',
                'temperature': temperature,
                'error_type': type(e).__name__,
                'prompt': prompt
            },
            original_error=e
        ) 