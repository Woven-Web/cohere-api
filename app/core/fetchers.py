import requests
from typing import Dict, Any, Optional, Callable, List, Union
import logging
from functools import wraps
import time
import os
from urllib.parse import urlparse
import asyncio
import playwright_aws_lambda
from playwright_aws_lambda.utils import PlaywrightError

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
    
    def __init__(self, 
                 message: str,
                 url: Optional[str] = None,
                 status_code: Optional[int] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.url = url
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = time.time()
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Format error message with relevant context."""
        parts = [self.message]
        
        if self.url:
            parts.append(f"URL: {self.url}")
        
        if self.status_code:
            status_message = get_error_message(self.status_code)
            parts.append(f"Status {self.status_code}: {status_message}")
        
        if self.details:
            # Only include details that help understand what went wrong
            relevant_details = {
                k: v for k, v in self.details.items() 
                if k in {'current_attempt', 'missing_selectors', 'content_length', 'error_message'}
            }
            if relevant_details:
                parts.append(f"Details: {relevant_details}")
        
        return " | ".join(parts)

def get_error_message(status_code: int) -> str:
    """Get a descriptive error message for HTTP status codes."""
    messages = {
        400: "Bad request - check URL format and parameters",
        401: "Authentication required",
        403: "Access forbidden - site may be blocking access",
        404: "Page not found",
        429: "Too many requests - rate limited",
        500: "Server error",
        502: "Bad gateway - server error",
        503: "Service unavailable",
        504: "Gateway timeout"
    }
    return messages.get(status_code, f"HTTP {status_code}")

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
    timeout_ms: int = 30000,  
    wait_until: str = "networkidle",  # Default to networkidle for dynamic content
    wait_for_selectors: Optional[List[str]] = None,
    max_retries: int = 2,
    retry_delay: int = 1,
    user_agent: Optional[str] = None,
    viewport: Optional[Dict[str, int]] = None,
    javascript_enabled: bool = True,
    ignore_https_errors: bool = False,
    scroll_to_bottom: bool = False,
    dynamic_wait_time: int = 5000,
    required_selectors: Optional[List[str]] = None,
    blocked_selectors: Optional[List[str]] = None,
    error_texts: Optional[List[str]] = None,
    cookie_accept_selector: Optional[str] = None
) -> str:
    """
    Generic Playwright-based content fetcher with configurable behavior for dynamic websites.
    
    Args:
        url: The URL to fetch content from
        timeout_ms: Page load timeout in milliseconds
        wait_until: Page load state to wait for (load, domcontentloaded, networkidle)
        wait_for_selectors: List of CSS selectors to wait for
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        user_agent: Custom user agent string
        viewport: Custom viewport dimensions
        javascript_enabled: Whether to enable JavaScript
        ignore_https_errors: Whether to ignore HTTPS errors
        scroll_to_bottom: Whether to scroll to bottom for lazy-loaded content
        dynamic_wait_time: Additional wait time for dynamic content in ms
        required_selectors: List of selectors that must be present in the page
        blocked_selectors: List of selectors that indicate blocked/login-required content
        error_texts: List of error message texts to check for
        cookie_accept_selector: Selector for cookie consent button
        
    Returns:
        The HTML content as a string
        
    Raises:
        FetchError: If the page cannot be loaded or content cannot be extracted
    """
    logger.info(f"Fetching content from {url} using Playwright")
    
    for attempt in range(max_retries + 1):
        try:
            browser = await playwright_aws_lambda.async_playwright()
            
            try:
                # Basic context configuration
                context = await browser.new_context(
                    user_agent=user_agent or DEFAULT_HEADERS['User-Agent'],
                    viewport=viewport or {'width': 1920, 'height': 1080},
                    ignore_https_errors=ignore_https_errors,
                    java_script_enabled=javascript_enabled,
                    locale='en-US'
                )
                
                # Add common headers
                await context.set_extra_http_headers(DEFAULT_HEADERS)
                
                page = await context.new_page()
                page.set_default_navigation_timeout(timeout_ms)
                page.set_default_timeout(timeout_ms)
                
                # Navigate to URL
                logger.debug(f"Navigating to {url}")
                response = await page.goto(url, wait_until=wait_until)
                
                if not response:
                    raise FetchError(
                        "Failed to get page response",
                        url=url,
                        details={'current_attempt': attempt + 1}
                    )
                
                if response.status >= 400:
                    raise FetchError(
                        "HTTP error response",
                        url=url,
                        status_code=response.status,
                        details={'current_attempt': attempt + 1}
                    )
                
                # Handle cookie consent if configured
                if cookie_accept_selector:
                    try:
                        await page.click(cookie_accept_selector, timeout=5000)
                        logger.debug("Accepted cookies")
                    except Exception as e:
                        logger.debug(f"No cookie banner found or unable to accept: {str(e)}")
                
                # Wait for load state
                await page.wait_for_load_state(wait_until)
                
                # Check for blocked content first
                if blocked_selectors:
                    for selector in blocked_selectors:
                        try:
                            blocked_element = await page.wait_for_selector(selector, timeout=2000)
                            if blocked_element:
                                raise FetchError(
                                    "Content access blocked",
                                    error_type='BLOCKED',
                                    url=url,
                                    details={'blocked_by': selector}
                                )
                        except PlaywrightError:
                            continue
                
                # Simplify selector checking to focus on what's missing
                if wait_for_selectors:
                    missing = []
                    for selector in wait_for_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=timeout_ms)
                        except Exception:
                            missing.append(selector)
                    
                    if missing:
                        raise FetchError(
                            "Failed to find expected content",
                            url=url,
                            details={'missing_selectors': missing}
                        )
                
                # Handle dynamic content loading
                if scroll_to_bottom:
                    logger.debug("Scrolling page for dynamic content")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                if dynamic_wait_time > 0:
                    logger.debug(f"Waiting {dynamic_wait_time}ms for dynamic content")
                    await page.wait_for_timeout(dynamic_wait_time)
                
                # Verify required content is present
                if required_selectors:
                    missing_selectors = []
                    for selector in required_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                        except Exception:
                            missing_selectors.append(selector)
                    
                    if missing_selectors:
                        raise FetchError(
                            "Required content not found",
                            error_type='VALIDATION',
                            url=url,
                            details={'missing_selectors': missing_selectors}
                        )
                
                # Check for error messages
                if error_texts:
                    for error_text in error_texts:
                        try:
                            error_element = await page.query_selector(f"text={error_text}")
                            if error_element:
                                raise FetchError(
                                    f"Access error: {error_text}",
                                    error_type='BLOCKED',
                                    url=url,
                                    details={'error_message': error_text}
                                )
                        except PlaywrightError:
                            continue
                
                # Simplify content validation
                content = await page.content()
                if not content or len(content.strip()) < 100:
                    raise FetchError(
                        "Retrieved content is too short or empty",
                        url=url,
                        details={'content_length': len(content) if content else 0}
                    )
                
                return content
                
            except PlaywrightError as e:
                raise FetchError(
                    f"Playwright error: {str(e)}",
                    error_type='DYNAMIC',
                    url=url,
                    details={'playwright_error': str(e)}
                )
                
            finally:
                if 'context' in locals():
                    await context.close()
                if 'browser' in locals():
                    await browser.close()
                    
        except FetchError as e:
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            raise
            
        except Exception as e:
            raise FetchError(
                f"Unexpected error: {str(e)}",
                error_type='DYNAMIC',
                url=url,
                details={'error': str(e)}
            ) 