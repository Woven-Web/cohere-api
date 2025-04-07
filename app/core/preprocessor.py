import logging
from bs4 import BeautifulSoup, Comment
import html2text
import markdownify

logger = logging.getLogger(__name__)

class PreprocessingError(Exception):
    """Exception raised for errors during HTML preprocessing."""
    pass

def preprocess_html(
    html_content: str, 
    strategy: str = 'markdownify',
    max_length: int = 8000
) -> str:
    """
    Clean and convert HTML content to Markdown, focusing on essential content.
    
    Args:
        html_content: The raw HTML content
        strategy: Conversion library to use ('markdownify' or 'html2text')
        max_length: Maximum length of the resulting Markdown
        
    Returns:
        Cleaned Markdown content
        
    Raises:
        PreprocessingError: If parsing or conversion fails
    """
    try:
        logger.info(f"Starting HTML preprocessing using {strategy}")
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove non-content elements
        for element in soup.find_all(['script', 'style', 'iframe', 'noscript']):
            element.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            
        # Remove common non-content areas
        for selector in [
            '[role="banner"]',  # Site header
            '[role="navigation"]',  # Navigation
            '[role="complementary"]',  # Sidebars
            '[role="contentinfo"]',  # Footer
            '[aria-label="Advertisement"]',  # Ads
        ]:
            for element in soup.select(selector):
                element.decompose()
                
        # Clean up attributes, keeping only essential ones
        for tag in soup.find_all(True):
            allowed_attrs = ['href', 'src', 'alt', 'title', 'datetime']
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}
            
        # Get main content
        main = soup.find(['main', '[role="main"]']) or soup.find('body') or soup
        processed_html = str(main)
        logger.debug(f"Processed HTML (first 500 chars): {processed_html[:500]}")

        # Convert to Markdown
        if strategy == 'markdownify':
            markdown_content = markdownify.markdownify(
                processed_html,
                heading_style="ATX",
                strip=['form']  # Remove forms as they rarely contain relevant content
            )
        elif strategy == 'html2text':
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.body_width = 0  # Don't wrap text
            markdown_content = h.handle(processed_html)
        else:
            raise ValueError(f"Unsupported preprocessing strategy: {strategy}")

        # Clean up whitespace
        markdown_content = '\n'.join(
            line.strip() for line in markdown_content.splitlines() 
            if line.strip()
        )
        markdown_content = markdown_content.replace('\n\n\n', '\n\n')

        # Truncate if needed
        if len(markdown_content) > max_length:
            logger.warning(f"Truncating content from {len(markdown_content)} to {max_length} characters")
            markdown_content = markdown_content[:max_length] + "... [Content truncated]"
            
        logger.info(f"Preprocessing completed. Output length: {len(markdown_content)}")
        return markdown_content

    except Exception as e:
        logger.error(f"Error during HTML preprocessing: {str(e)}", exc_info=True)
        raise PreprocessingError(f"Failed to preprocess HTML: {str(e)}") 