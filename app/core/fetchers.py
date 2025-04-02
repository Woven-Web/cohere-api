import requests
from typing import Dict, Any, Optional, Callable, List, Union
import logging
from functools import wraps
import time
import os
from urllib.parse import urlparse
import asyncio
from playwright.async_api import async_playwright, Error as PlaywrightError

# Configure logger
logger = logging.getLogger(__name__)

# Default headers
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

class FetchError(Exception):
    """Exception raised for errors in the content fetching process."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, url: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.url = url
        super().__init__(self.message)
        
    def __str__(self) -> str:
        base_msg = self.message
        if self.status_code:
            base_msg = f"{base_msg} (Status: {self.status_code})"
        if self.url:
            base_msg = f"{base_msg} - URL: {self.url}"
        return base_msg

def get_error_message(status_code: int) -> str:
    """Get a descriptive error message for common HTTP status codes."""
    
    status_messages = {
        400: "Bad Request - The server could not understand the request",
        401: "Unauthorized - Authentication is required",
        403: "Forbidden - The server understood but refuses to authorize the request",
        404: "Not Found - The requested resource could not be found",
        429: "Too Many Requests - Rate limit exceeded",
        500: "Internal Server Error - The server encountered an unexpected condition",
        502: "Bad Gateway - The server received an invalid response from an upstream server",
        503: "Service Unavailable - The server is temporarily unavailable",
        504: "Gateway Timeout - The server did not receive a timely response",
    }
    
    return status_messages.get(status_code, f"HTTP Error {status_code}")

async def fetch_http_content(
    url: str, 
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: int = 1,
    headers: Optional[Dict[str, str]] = None,
    verify_ssl: bool = True
) -> str:
    """
    Fetch HTML content from a URL using the requests library.
    
    Args:
        url: The URL to fetch content from
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Delay between retries in seconds
        headers: Optional custom HTTP headers
        verify_ssl: Whether to verify SSL certificates
        
    Returns:
        The HTML content as a string
        
    Raises:
        FetchError: If the request fails or returns an error status
    """
    # Attach error message helper to the function for testing
    fetch_http_content.get_error_message = get_error_message
    
    # Merge default headers with custom headers
    request_headers = DEFAULT_HEADERS.copy()
    if headers:
        request_headers.update(headers)
    
    # Parse and validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Invalid URL format")
    except Exception as e:
        logger.error(f"Invalid URL: {url} - {str(e)}")
        raise FetchError(f"Invalid URL format: {str(e)}", url=url)
    
    # Attempt request with retries for specific errors
    retries = 0
    last_error = None
    
    while retries <= max_retries:
        try:
            logger.info(f"Fetching content from {url} (attempt {retries + 1}/{max_retries + 1})")
            
            response = requests.get(
                url, 
                timeout=timeout, 
                headers=request_headers,
                verify=verify_ssl
            )
            
            # Check if the response contains HTML
            content_type = response.headers.get('Content-Type', '')
            if not ('text/html' in content_type.lower() or 'application/xhtml+xml' in content_type.lower()):
                logger.warning(f"Unexpected content type: {content_type} from {url}")
            
            # Check status code
            if response.status_code >= 400:
                error_message = get_error_message(response.status_code)
                # Only retry on server errors (5xx)
                if 500 <= response.status_code < 600 and retries < max_retries:
                    last_error = FetchError(
                        f"Server error: {error_message}", 
                        status_code=response.status_code,
                        url=url
                    )
                    retries += 1
                    time.sleep(retry_delay)
                    continue
                else:
                    # For client errors (4xx) or if we're out of retries, raise immediately
                    raise FetchError(
                        f"HTTP error: {error_message}", 
                        status_code=response.status_code,
                        url=url
                    )
            
            # Attempt to detect encoding issues
            try:
                response.encoding = response.apparent_encoding
            except Exception:
                logger.warning(f"Could not determine encoding for {url}, using default")
            
            # Make sure the response has content
            if not response.text or len(response.text) < 10:
                logger.warning(f"Empty or very short response from {url}")
            
            return response.text
            
        except requests.Timeout as e:
            last_error = FetchError(f"Request timed out after {timeout} seconds", url=url)
            logger.warning(f"Request timeout for {url}: {str(e)}")
            
        except requests.ConnectionError as e:
            last_error = FetchError(f"Connection error: {str(e)}", url=url)
            logger.warning(f"Connection error for {url}: {str(e)}")
            
        except requests.RequestException as e:
            last_error = FetchError(f"Request error: {str(e)}", url=url)
            logger.warning(f"Request error for {url}: {str(e)}")
            
        except FetchError:
            # Re-raise FetchError immediately without retrying
            raise
            
        except Exception as e:
            last_error = FetchError(f"Unexpected error: {str(e)}", url=url)
            logger.error(f"Unexpected error fetching {url}: {str(e)}", exc_info=True)
        
        # Retry with delay if we haven't exceeded max retries
        if retries < max_retries:
            retries += 1
            time.sleep(retry_delay)
        else:
            break
    
    # If we got here, all retry attempts failed
    if last_error:
        logger.error(f"Failed to fetch {url} after {max_retries + 1} attempts: {str(last_error)}")
        raise last_error
    else:
        # This should never happen, but just in case
        raise FetchError(f"Failed to fetch {url} after {max_retries + 1} attempts", url=url)

async def fetch_playwright_content(
    url: str,
    timeout_ms: int = 60000,  # Increased to 60 seconds
    wait_until: str = "networkidle",
    wait_for_selectors: Optional[List[str]] = None,
    max_retries: int = 2,
    retry_delay: int = 1,
    user_agent: Optional[str] = None,
    viewport: Optional[Dict[str, int]] = None,
    javascript_enabled: bool = True,
    ignore_https_errors: bool = False
) -> str:
    """
    Fetch HTML content from a URL using Playwright browser automation.
    
    Args:
        url: The URL to fetch content from
        timeout_ms: Page load timeout in milliseconds (default: 60000)
        wait_until: Page load state to wait for (default: networkidle)
        wait_for_selectors: List of CSS selectors to wait for (default: None)
        max_retries: Maximum number of retry attempts (default: 2)
        retry_delay: Delay between retries in seconds (default: 1)
        user_agent: Custom user agent string (default: None)
        viewport: Custom viewport dimensions (default: None)
        javascript_enabled: Whether to enable JavaScript (default: True)
        ignore_https_errors: Whether to ignore HTTPS errors (default: False)
        
    Returns:
        The HTML content as a string
        
    Raises:
        FetchError: If the page cannot be loaded or content cannot be extracted
    """
    logger.info(f"Fetching content from {url} using Playwright")
    
    for attempt in range(max_retries + 1):
        try:
            async with async_playwright() as p:
                logger.debug(f"Launching headless browser (attempt {attempt + 1}/{max_retries + 1})")
                browser = await p.chromium.launch(headless=True)
                
                try:
                    context = await browser.new_context(
                        user_agent=user_agent or DEFAULT_HEADERS['User-Agent'],
                        viewport=viewport or {'width': 1920, 'height': 1080},
                        ignore_https_errors=ignore_https_errors,
                        java_script_enabled=javascript_enabled
                    )
                    
                    page = await context.new_page()
                    
                    # Set default navigation timeout
                    page.set_default_navigation_timeout(timeout_ms)
                    page.set_default_timeout(timeout_ms)
                    
                    # Navigate to the URL
                    logger.debug(f"Navigating to {url}")
                    await page.goto(url, wait_until=wait_until)
                    
                    # Wait for network to be idle
                    logger.debug(f"Waiting for page load state: {wait_until}")
                    await page.wait_for_load_state(wait_until)
                    
                    # Wait for any specified selectors
                    if wait_for_selectors:
                        for selector in wait_for_selectors:
                            try:
                                logger.debug(f"Waiting for selector: {selector}")
                                await page.wait_for_selector(selector, timeout=timeout_ms)
                            except PlaywrightError as e:
                                logger.warning(f"Selector '{selector}' not found: {str(e)}")
                    
                    # Additional wait for dynamic content
                    await asyncio.sleep(2)  # Short delay for any final dynamic updates
                    
                    # Extract HTML content
                    logger.debug("Extracting HTML content")
                    content = await page.content()
                    
                    # Verify we got meaningful content
                    if not content or len(content.strip()) < 100:
                        raise FetchError(f"Retrieved content too short from {url}")
                    
                    return content
                    
                finally:
                    await browser.close()
                    
        except PlaywrightError as e:
            last_error = f"Playwright error: {str(e)}"
            logger.warning(f"Playwright error fetching {url}: {str(e)}")
            
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(f"Error fetching {url}: {str(e)}", exc_info=True)
        
        if attempt < max_retries:
            await asyncio.sleep(retry_delay)
        else:
            raise FetchError(f"Failed to fetch {url} after {max_retries + 1} attempts: {last_error}", url=url) 