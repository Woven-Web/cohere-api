"""Tests for the fetchers module."""

import pytest
from unittest.mock import patch, MagicMock
import requests
from playwright.async_api import Error as PlaywrightError
from app.core.fetchers import (
    fetch_http_content,
    fetch_playwright_content,
    FetchError,
    DEFAULT_HEADERS
)

# Test URLs
VALID_URL = "https://example.com"
INVALID_URL = "not-a-url"
TIMEOUT_URL = "https://timeout.example.com"
CONNECTION_ERROR_URL = "https://connection-error.example.com"

# Sample HTML content
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body><h1>Hello World</h1></body>
</html>
"""

# Mock classes for Playwright tests
class MockPage:
    def __init__(self, content=SAMPLE_HTML, should_fail=False, fail_with=None, fail_at=None):
        self._content = content
        self.should_fail = should_fail
        self.fail_with = fail_with
        self.fail_at = fail_at or "navigation"  # "navigation", "load_state", "content"
        self.closed = False
    
    async def goto(self, url, **kwargs):
        if self.should_fail and self.fail_at == "navigation":
            if self.fail_with:
                raise self.fail_with("Navigation failed")
            raise PlaywrightError("Navigation failed")
    
    async def wait_for_load_state(self, state, **kwargs):
        if self.should_fail and self.fail_at == "load_state":
            raise PlaywrightError("Load state timeout")
    
    async def wait_for_selector(self, selector, **kwargs):
        if self.should_fail:
            raise PlaywrightError(f"Selector '{selector}' not found")
    
    async def content(self):
        if self.should_fail and self.fail_at == "content":
            raise PlaywrightError("Failed to get content")
        return self._content
    
    async def close(self):
        self.closed = True

class MockContext:
    def __init__(self, page=None):
        self.page = page or MockPage()
    
    async def new_page(self):
        return self.page
    
    async def close(self):
        pass

class MockBrowser:
    def __init__(self, context=None):
        self.context = context or MockContext()
        self.closed = False
    
    async def new_context(self, **kwargs):
        return self.context
    
    async def close(self):
        self.closed = True

class MockPlaywright:
    def __init__(self, browser=None):
        self.browser = browser or MockBrowser()
        self.chromium = self
    
    async def launch(self, **kwargs):
        return self.browser
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.mark.asyncio
async def test_fetch_http_content_success():
    """Test successful HTTP content fetching."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.apparent_encoding = 'utf-8'
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        content = await fetch_http_content(VALID_URL)
        
        assert content == SAMPLE_HTML
        mock_get.assert_called_once_with(
            VALID_URL,
            timeout=30,
            headers=DEFAULT_HEADERS,
            verify=True
        )

@pytest.mark.asyncio
async def test_fetch_http_content_invalid_url():
    """Test handling of invalid URLs."""
    with pytest.raises(FetchError) as exc_info:
        await fetch_http_content(INVALID_URL)
    assert "Invalid URL format" in str(exc_info.value)
    assert INVALID_URL in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_http_content_timeout():
    """Test handling of request timeouts."""
    with patch('requests.get', side_effect=requests.Timeout("Connection timed out")):
        with pytest.raises(FetchError) as exc_info:
            await fetch_http_content(TIMEOUT_URL, max_retries=1)
        assert "Request timed out" in str(exc_info.value)
        assert TIMEOUT_URL in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_http_content_connection_error():
    """Test handling of connection errors."""
    with patch('requests.get', side_effect=requests.ConnectionError("Connection refused")):
        with pytest.raises(FetchError) as exc_info:
            await fetch_http_content(CONNECTION_ERROR_URL, max_retries=1)
        assert "Connection error" in str(exc_info.value)
        assert CONNECTION_ERROR_URL in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_http_content_client_error():
    """Test handling of client errors (4xx)."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.headers = {'Content-Type': 'text/html'}
    
    with patch('requests.get', return_value=mock_response):
        with pytest.raises(FetchError) as exc_info:
            await fetch_http_content(VALID_URL)
        assert "Not Found" in str(exc_info.value)
        assert "404" in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_http_content_server_error_retry():
    """Test retry behavior for server errors (5xx)."""
    mock_response_error = MagicMock()
    mock_response_error.status_code = 500
    mock_response_error.headers = {'Content-Type': 'text/html'}
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.text = SAMPLE_HTML
    mock_response_success.headers = {'Content-Type': 'text/html'}
    mock_response_success.apparent_encoding = 'utf-8'
    
    with patch('requests.get', side_effect=[mock_response_error, mock_response_success]) as mock_get:
        content = await fetch_http_content(VALID_URL, max_retries=2, retry_delay=0)
        
        assert content == SAMPLE_HTML
        assert mock_get.call_count == 2

@pytest.mark.asyncio
async def test_fetch_http_content_custom_headers():
    """Test using custom headers."""
    custom_headers = {'X-Custom': 'test'}
    expected_headers = {**DEFAULT_HEADERS, **custom_headers}
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.apparent_encoding = 'utf-8'
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        await fetch_http_content(VALID_URL, headers=custom_headers)
        
        mock_get.assert_called_once_with(
            VALID_URL,
            timeout=30,
            headers=expected_headers,
            verify=True
        )

@pytest.mark.asyncio
async def test_fetch_http_content_non_html():
    """Test handling of non-HTML content types."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Not HTML"
    mock_response.headers = {'Content-Type': 'text/plain'}
    mock_response.apparent_encoding = 'utf-8'
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        content = await fetch_http_content(VALID_URL)
        
        assert content == "Not HTML"
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_http_content_empty_response():
    """Test handling of empty responses."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.apparent_encoding = 'utf-8'
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        content = await fetch_http_content(VALID_URL)
        
        assert content == ""
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_http_content_encoding_error():
    """Test handling of encoding detection errors."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = SAMPLE_HTML
    mock_response.headers = {'Content-Type': 'text/html'}
    mock_response.apparent_encoding = None  # This will cause an error when accessed
    
    with patch('requests.get', return_value=mock_response) as mock_get:
        content = await fetch_http_content(VALID_URL)
        
        assert content == SAMPLE_HTML
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_playwright_content_success():
    """Test successful content fetching with Playwright."""
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    async def mock_async_playwright():
        return mock_playwright
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        content = await fetch_playwright_content(VALID_URL)
        
        assert content == SAMPLE_HTML
        assert mock_browser.closed  # Verify browser was closed

@pytest.mark.asyncio
async def test_fetch_playwright_content_with_custom_timeout():
    """Test Playwright fetching with custom timeout."""
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        await fetch_playwright_content(VALID_URL, timeout_ms=60000)
        # Success is enough, as we can't easily verify the timeout was used

@pytest.mark.asyncio
async def test_fetch_playwright_content_navigation_failure():
    """Test handling of navigation failures."""
    mock_page = MockPage(should_fail=True, fail_with=PlaywrightError)
    mock_browser = MockBrowser(MockContext(mock_page))
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content(VALID_URL)
        
        assert "Navigation failed" in str(exc_info.value)
        assert mock_browser.closed  # Verify cleanup occurred

@pytest.mark.asyncio
async def test_fetch_playwright_content_load_timeout():
    """Test handling of load state timeout."""
    mock_page = MockPage(should_fail=True, fail_at="load_state")
    mock_browser = MockBrowser(MockContext(mock_page))
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content(VALID_URL)
        
        assert "Timeout" in str(exc_info.value)
        assert mock_browser.closed

@pytest.mark.asyncio
async def test_fetch_playwright_content_extraction_failure():
    """Test handling of content extraction failure."""
    mock_page = MockPage(should_fail=True, fail_at="content")
    mock_browser = MockBrowser(MockContext(mock_page))
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content(VALID_URL)
        
        assert "Failed to get content" in str(exc_info.value)
        assert mock_browser.closed

@pytest.mark.asyncio
async def test_fetch_playwright_content_launch_failure():
    """Test handling of browser launch failure."""
    async def mock_launch(**kwargs):
        raise PlaywrightError("Failed to launch browser")
    
    mock_playwright = MockPlaywright()
    mock_playwright.launch = mock_launch
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content(VALID_URL)
        
        assert "Failed to launch browser" in str(exc_info.value)

@pytest.mark.asyncio
async def test_fetch_playwright_content_with_selectors():
    """Test content fetching with wait for selectors."""
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        content = await fetch_playwright_content(VALID_URL, wait_for_selectors=["h1", ".content"])
        
        assert content == SAMPLE_HTML
        assert mock_browser.closed

@pytest.mark.asyncio
async def test_fetch_playwright_content_with_custom_viewport():
    """Test content fetching with custom viewport."""
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        content = await fetch_playwright_content(VALID_URL, viewport={"width": 1920, "height": 1080})
        
        assert content == SAMPLE_HTML
        assert mock_browser.closed

@pytest.mark.asyncio
async def test_fetch_playwright_content_with_custom_user_agent():
    """Test content fetching with custom user agent."""
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    with patch('app.core.fetchers.async_playwright', return_value=mock_playwright):
        content = await fetch_playwright_content(VALID_URL, user_agent="Custom User Agent")
        
        assert content == SAMPLE_HTML
        assert mock_browser.closed 