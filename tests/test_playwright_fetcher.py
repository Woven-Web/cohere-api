import pytest
from unittest import mock
import asyncio
from playwright.async_api import Error as PlaywrightError
from app.core.fetchers import fetch_playwright_content, FetchError
from contextlib import asynccontextmanager

# Mock for Playwright Browser
class MockBrowser:
    def __init__(self, mock_html=None, should_fail=False, fail_with=None):
        self.mock_html = mock_html or "<html><body>Dynamic content</body></html>"
        self.should_fail = should_fail
        self.fail_with = fail_with
        self.close_called = False
    
    async def new_context(self, **kwargs):
        return MockContext(self.mock_html, self.should_fail, self.fail_with)
    
    async def close(self):
        self.close_called = True

# Mock for Playwright Context
class MockContext:
    def __init__(self, mock_html, should_fail, fail_with):
        self.mock_html = mock_html
        self.should_fail = should_fail
        self.fail_with = fail_with
        self.closed = False
    
    async def new_page(self):
        return MockPage(self.mock_html, self.should_fail, self.fail_with)
    
    async def close(self):
        self.closed = True

# Mock for Playwright Page
class MockPage:
    def __init__(self, mock_html, should_fail, fail_with):
        self.mock_html = mock_html
        self.should_fail = should_fail
        self.fail_with = fail_with
        self.goto_called = False
        self.wait_for_load_state_called = False
        self.closed = False
    
    async def goto(self, url, **kwargs):
        self.goto_called = True
        if self.should_fail and self.fail_with == 'goto':
            raise PlaywrightError("Navigation failed")
    
    async def wait_for_load_state(self, state="networkidle", **kwargs):
        self.wait_for_load_state_called = True
        if self.should_fail and self.fail_with == 'wait_for_load_state':
            raise PlaywrightError("Timeout waiting for load state")
    
    async def content(self):
        if self.should_fail and self.fail_with == 'content':
            raise PlaywrightError("Failed to get content")
        return self.mock_html
    
    async def close(self):
        self.closed = True

# Mock for Playwright
class MockPlaywright:
    def __init__(self, mock_browser):
        self.chromium = MockChromium(mock_browser)

# Mock for Chromium
class MockChromium:
    def __init__(self, mock_browser):
        self.mock_browser = mock_browser
    
    async def launch(self, **kwargs):
        return self.mock_browser

@pytest.mark.asyncio
async def test_fetch_playwright_content_success():
    # Mock successful scenario
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function
        html = await fetch_playwright_content("https://example.com")
        
        # Verify the result
        assert html == "<html><body>Dynamic content</body></html>"
        
        # Verify browser was closed properly
        assert mock_browser.close_called

@pytest.mark.asyncio
async def test_fetch_playwright_content_with_custom_timeout():
    # Mock successful scenario
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function with custom timeout
        await fetch_playwright_content("https://example.com", timeout_ms=60000)
        
        # Verify the timeout was passed (would need to inspect the actual implementation)
        # This test provides a framework that implementation can use

@pytest.mark.asyncio
async def test_fetch_playwright_content_navigation_failure():
    # Mock navigation failure
    mock_browser = MockBrowser(should_fail=True, fail_with='goto')
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function and expect it to raise FetchError
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content("https://example.com")
        
        # Verify the error message
        assert "Navigation failed" in str(exc_info.value)
        
        # Verify browser was closed even after failure
        assert mock_browser.close_called

@pytest.mark.asyncio
async def test_fetch_playwright_content_load_timeout():
    # Mock load state timeout
    mock_browser = MockBrowser(should_fail=True, fail_with='wait_for_load_state')
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function and expect it to raise FetchError
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content("https://example.com")
        
        # Verify the error message
        assert "Timeout" in str(exc_info.value)
        
        # Verify browser was closed
        assert mock_browser.close_called

@pytest.mark.asyncio
async def test_fetch_playwright_content_extraction_failure():
    # Mock content extraction failure
    mock_browser = MockBrowser(should_fail=True, fail_with='content')
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function and expect it to raise FetchError
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content("https://example.com")
        
        # Verify the error message
        assert "Failed to get content" in str(exc_info.value)
        
        # Verify browser was closed
        assert mock_browser.close_called

@pytest.mark.asyncio
async def test_fetch_playwright_content_launch_failure():
    # Mock browser launch failure
    mock_browser = MockBrowser()
    mock_playwright = MockPlaywright(mock_browser)
    
    @asynccontextmanager
    async def mock_async_playwright():
        raise PlaywrightError("Failed to launch browser")
        yield mock_playwright
    
    with mock.patch('app.core.fetchers.async_playwright', mock_async_playwright):
        # Call the function and expect it to raise FetchError
        with pytest.raises(FetchError) as exc_info:
            await fetch_playwright_content("https://example.com")
        
        # Verify the error message
        assert "Failed to launch browser" in str(exc_info.value) 