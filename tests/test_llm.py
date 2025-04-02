"""Tests for the LLM module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
from app.core.llm import (
    init_gemini,
    create_extraction_prompt,
    extract_event_info,
    APIKeyError,
    ContentFilterError,
    ResponseParsingError,
    LLMError
)
import google.generativeai as genai

# Sample test data
SAMPLE_CONTENT = """
Join us for our Annual Tech Conference!
Date: March 15, 2024 from 9:00 AM to 5:00 PM EST
Location: Tech Hub, 123 Innovation Street, Silicon Valley
"""

SAMPLE_CUSTOM_INSTRUCTIONS = "Focus on extracting the exact times and location details."

SAMPLE_RESPONSE = {
    "title": "Annual Tech Conference",
    "description": "Tech conference event",
    "start_datetime": "2024-03-15T09:00:00-05:00",
    "end_datetime": "2024-03-15T17:00:00-05:00",
    "location": "Tech Hub, 123 Innovation Street, Silicon Valley"
}

@pytest.mark.asyncio
async def test_init_gemini_success():
    """Test successful Gemini API initialization."""
    with patch('google.generativeai.configure') as mock_configure:
        init_gemini("test_api_key")
        mock_configure.assert_called_once_with(api_key="test_api_key")

@pytest.mark.asyncio
async def test_init_gemini_failure():
    """Test Gemini API initialization failure."""
    with patch('google.generativeai.configure', side_effect=Exception("API Error")):
        with pytest.raises(APIKeyError) as exc_info:
            init_gemini("invalid_key")
        assert "Failed to initialize Gemini API" in str(exc_info.value)

def test_create_extraction_prompt():
    """Test prompt creation with and without custom instructions."""
    # Test with custom instructions
    prompt = create_extraction_prompt(SAMPLE_CONTENT, SAMPLE_CUSTOM_INSTRUCTIONS)
    assert SAMPLE_CONTENT in prompt
    assert SAMPLE_CUSTOM_INSTRUCTIONS in prompt
    
    # Test without custom instructions
    prompt = create_extraction_prompt(SAMPLE_CONTENT)
    assert SAMPLE_CONTENT in prompt
    assert "Extract all available event information" in prompt

@pytest.mark.asyncio
async def test_extract_event_info_success():
    """Test successful event information extraction."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(SAMPLE_RESPONSE)
    
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        result = await extract_event_info(
            SAMPLE_CONTENT,
            "test_api_key",
            SAMPLE_CUSTOM_INSTRUCTIONS
        )
        
        assert result == SAMPLE_RESPONSE
        assert result["title"] == "Annual Tech Conference"
        assert result["start_datetime"] == "2024-03-15T09:00:00-05:00"

@pytest.mark.asyncio
async def test_extract_event_info_empty_response():
    """Test handling of empty API response."""
    mock_response = MagicMock()
    mock_response.text = ""
    
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        with pytest.raises(ResponseParsingError) as exc_info:
            await extract_event_info(SAMPLE_CONTENT, "test_api_key")
        assert "Empty response from Gemini API" in str(exc_info.value)

@pytest.mark.asyncio
async def test_extract_event_info_invalid_json():
    """Test handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.text = "Invalid JSON"
    
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        with pytest.raises(ResponseParsingError) as exc_info:
            await extract_event_info(SAMPLE_CONTENT, "test_api_key")
        assert "Failed to parse response as JSON" in str(exc_info.value)

@pytest.mark.asyncio
async def test_extract_event_info_content_filtered():
    """Test handling of content filtering."""
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(side_effect=Exception("Content blocked by safety settings"))
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        with pytest.raises(ContentFilterError) as exc_info:
            await extract_event_info(SAMPLE_CONTENT, "test_api_key")
        assert "Content filtered by Gemini API" in str(exc_info.value)

@pytest.mark.asyncio
async def test_extract_event_info_missing_fields():
    """Test handling of response with missing fields."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({"title": "Test Event"})  # Missing other fields
    
    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        result = await extract_event_info(SAMPLE_CONTENT, "test_api_key")
        
        # Verify all required fields exist with None for missing ones
        assert result["title"] == "Test Event"
        assert result["description"] is None
        assert result["start_datetime"] is None
        assert result["end_datetime"] is None
        assert result["location"] is None

@pytest.mark.asyncio
async def test_extract_event_info_retry():
    """Test retry behavior on temporary failures."""
    mock_model = MagicMock()
    # Fail twice, succeed on third try
    mock_response = MagicMock()
    mock_response.text = json.dumps(SAMPLE_RESPONSE)
    mock_model.generate_content_async = AsyncMock(side_effect=[
        Exception("Temporary error"),
        Exception("Temporary error"),
        mock_response
    ])
    
    with patch('google.generativeai.GenerativeModel', return_value=mock_model), \
         patch('app.core.llm.init_gemini'):
        
        result = await extract_event_info(SAMPLE_CONTENT, "test_api_key")
        
        assert result == SAMPLE_RESPONSE
        assert mock_model.generate_content_async.call_count == 3 