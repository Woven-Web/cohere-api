import logging
import random
import time
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Error as PlaywrightError
import httpx
from .exceptions import FetchError

logger = logging.getLogger(__name__)

async def fetch_http_content(url: str) -> str:
    """
    Fetch webpage content using httpx.
    
    Args:
        url: The URL to fetch content from.
        
    Returns:
        str: The webpage content.
        
    Raises:
        FetchError: If there are issues fetching the content.
    """
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1'
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred while fetching {url}: {str(e)}")
        raise FetchError(f"Failed to fetch content: {str(e)}")
    except Exception as e:
        logger.error(f"Error occurred while fetching {url}: {str(e)}")
        raise FetchError(f"Failed to fetch content: {str(e)}")

async def fetch_playwright_content(url: str) -> str:
    """
    Fetch webpage content using Playwright with enhanced stealth features.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--disable-blink-features=AutomationControlled'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                device_scale_factor=1,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'DNT': '1'
                }
            )
            
            # Add minimal stealth script
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
            """)
            
            page = await context.new_page()
            
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            content = await page.content()
            
            await context.close()
            await browser.close()
            
            return content
            
    except Exception as e:
        if isinstance(e, FetchError):
            raise
        logger.error(f"Failed to fetch content using Playwright: {str(e)}", exc_info=True)
        raise FetchError(
            f"Failed to fetch content using Playwright: {str(e)}",
            details={
                'url': url,
                'error_type': type(e).__name__
            }
        ) 