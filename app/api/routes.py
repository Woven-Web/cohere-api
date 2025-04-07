from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from app.api.models import ScrapeRequest, ScrapeResponse, ErrorResponse
from app.core.fetchers import fetch_http_content, fetch_playwright_content, FetchError
from app.core.preprocessor import preprocess_html
from app.core.llm import extract_event_info, APIKeyError, ContentFilterError, ResponseParsingError, LLMError
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory rate limiting
RATE_LIMIT = 10  # requests per minute
RATE_WINDOW = 60  # seconds
request_counts = defaultdict(list)

async def check_rate_limit(request: Request):
    """Rate limiting middleware."""
    client_ip = request.client.host
    now = datetime.now()
    
    # Remove old timestamps
    request_counts[client_ip] = [ts for ts in request_counts[client_ip] 
                               if now - ts < timedelta(seconds=RATE_WINDOW)]
    
    # Check rate limit
    if len(request_counts[client_ip]) >= RATE_LIMIT:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Too many requests", "details": "Rate limit exceeded"}
        )
    
    # Add current timestamp
    request_counts[client_ip].append(now)

@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ErrorResponse, "description": "Validation Error"},
        429: {"model": ErrorResponse, "description": "Rate Limit Exceeded"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
        503: {"model": ErrorResponse, "description": "Service Unavailable"}
    },
    summary="Scrape event information from a webpage",
    description="Extracts event information (title, description, date/time, location) from a provided URL using web scraping and Gemini LLM"
)
async def scrape_website(request: ScrapeRequest, rate_limit: None = Depends(check_rate_limit)):
    """
    Extract event information from a webpage.
    
    This endpoint accepts a URL and scraping configuration, then:
    1. Fetches the webpage content (using Playwright if specified)
    2. Pre-processes the HTML to clean it
    3. Uses Google Gemini to extract structured event information
    4. Returns the event details in a standardized format
    
    All dates are returned in ISO 8601 format.
    """
    try:
        logger.info(f"Processing scrape request for URL: {request.url}")
        
        # Check if this is a Facebook URL - we don't support those
        if "facebook.com" in request.url:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Facebook URLs are not supported"}
            )
        
        # Fetch webpage content
        try:
            if request.use_playwright:
                logger.debug("Using Playwright for content fetching")
                content = await fetch_playwright_content(str(request.url))
                logger.debug(f"Fetched content length: {len(content)}")
                logger.debug(f"First 500 chars of content: {content[:500]}")
            else:
                logger.debug("Using HTTP client for content fetching")
                content = await fetch_http_content(str(request.url))
                logger.debug(f"Fetched content length: {len(content)}")
                logger.debug(f"First 500 chars of content: {content[:500]}")
        except FetchError as e:
            logger.error(f"Failed to fetch content from {request.url}: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Failed to fetch content", "details": str(e)}
            )
        
        # Preprocess HTML content
        try:
            logger.debug("Pre-processing HTML content")
            processed_content = preprocess_html(content)
            logger.debug(f"Processed content length: {len(processed_content)}")
            logger.debug(f"First 500 chars of processed content: {processed_content[:500]}")
        except Exception as e:
            logger.error(f"Failed to preprocess HTML: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to process content", "details": str(e)}
            )
        
        # Extract event information using Gemini
        try:
            logger.debug("Extracting event information using Gemini")
            event_info = await extract_event_info(
                processed_content,
                request.gemini_api_key,
                request.custom_instructions_text
            )
            
            # Convert to response model
            response = ScrapeResponse(**event_info)
            logger.info("Successfully extracted event information")
            logger.debug(f"Response data: {response.dict()}")
            return response
            
        except APIKeyError as e:
            logger.error(f"API key error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid API key", "details": str(e)}
            )
        except ContentFilterError as e:
            logger.error(f"Content filtered: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"error": "Content filtered", "details": str(e)}
            )
        except ResponseParsingError as e:
            logger.error(f"Response parsing error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"error": "Failed to parse response", "details": str(e)}
            )
        except LLMError as e:
            logger.error(f"LLM error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"error": "LLM service error", "details": str(e)}
            )
            
    except ValueError as e:
        # For validation errors
        logger.warning(f"Validation error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "Validation error", "details": str(e)}
        )
    except Exception as e:
        # For unexpected errors
        logger.error(f"Error processing scrape request: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Internal server error", "details": str(e)}
        ) 