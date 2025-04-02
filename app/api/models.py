from pydantic import BaseModel, HttpUrl, validator, Field
from typing import Optional
from datetime import datetime
import re

class ScrapeRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the webpage to scrape for event information")
    gemini_api_key: str = Field(..., description="Google Gemini API key for LLM processing")
    use_playwright: bool = Field(False, description="Whether to use Playwright for JavaScript-heavy sites")
    custom_instructions_text: Optional[str] = Field(None, description="Optional custom instructions for the LLM")
    
    @validator('gemini_api_key')
    def validate_api_key(cls, value):
        if not value or len(value) < 10:
            raise ValueError('Invalid API key format')
        return value
    
    @validator('url')
    def validate_url(cls, value):
        # Add additional URL validation if needed
        # The HttpUrl type already provides basic validation
        return value
    
    @validator('custom_instructions_text')
    def validate_instructions(cls, value):
        if value and len(value) > 1000:
            raise ValueError('Custom instructions too long (max 1000 characters)')
        return value

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com/event-page",
                "gemini_api_key": "your_api_key_here",
                "use_playwright": False,
                "custom_instructions_text": "Focus on extracting venue details"
            }
        }


class ScrapeResponse(BaseModel):
    title: Optional[str] = Field(None, description="Title of the event")
    description: Optional[str] = Field(None, description="Description of the event")
    start_datetime: Optional[str] = Field(None, description="Start date and time in ISO 8601 format")
    end_datetime: Optional[str] = Field(None, description="End date and time in ISO 8601 format")
    location: Optional[str] = Field(None, description="Location of the event")
    
    @validator('start_datetime', 'end_datetime', pre=True, always=True)
    def validate_datetime(cls, value):
        if not value:
            return None
            
        # Check if already in ISO 8601 format
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$'
        if re.match(iso_pattern, value):
            return value
            
        # If not, try to parse and convert to ISO format
        try:
            return datetime.fromisoformat(value).isoformat()
        except (ValueError, TypeError):
            try:
                # Try with more date formats
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%d-%m-%Y %H:%M'):
                    try:
                        return datetime.strptime(value, fmt).isoformat()
                    except ValueError:
                        continue
                raise ValueError(f"Invalid datetime format: {value}")
            except Exception:
                raise ValueError(f"Invalid datetime format: {value}")

    class Config:
        schema_extra = {
            "example": {
                "title": "Tech Conference 2023",
                "description": "Annual technology conference featuring workshops and speakers",
                "start_datetime": "2023-07-15T10:00:00Z",
                "end_datetime": "2023-07-15T18:00:00Z",
                "location": "123 Main St, San Francisco, CA 94105"
            }
        }


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Failed to fetch content",
                "details": "Connection timed out after 30 seconds"
            }
        } 