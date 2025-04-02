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
    remove_elements: list[str] = None,
    remove_by_selector: list[str] = None,
    max_length: int = 8000  # Maximum length to reduce token usage
) -> str:
    """
    Clean and convert HTML content to Markdown.

    Args:
        html_content: The raw HTML content.
        strategy: Conversion library to use ('markdownify' or 'html2text').
        remove_elements: List of HTML tag names to remove (e.g., ['script', 'style']).
        remove_by_selector: List of CSS selectors for elements to remove.
        max_length: Maximum length of the resulting Markdown.

    Returns:
        Cleaned Markdown content.

    Raises:
        PreprocessingError: If parsing or conversion fails.
    """
    if remove_elements is None:
        remove_elements = ['script', 'style', 'nav', 'footer', 'aside', 'form', 'iframe', 'noscript']
    
    if remove_by_selector is None:
        remove_by_selector = []
    
    try:
        logger.info(f"Starting HTML preprocessing using {strategy}")
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove specified tags
        for tag_name in remove_elements:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            
        # Remove elements by CSS selector
        for selector in remove_by_selector:
            for element in soup.select(selector):
                element.decompose()
                
        # Remove attributes that are not generally useful for LLMs
        for tag in soup.find_all(True):
            allowed_attrs = ['href', 'src', 'alt', 'title']
            tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed_attrs}
            
        # Get the cleaned HTML structure (usually focusing on body)
        body = soup.find('body')
        if not body:
            logger.warning("No <body> tag found in HTML. Using entire soup.")
            processed_html = str(soup)
        else:
            processed_html = str(body)

        # Convert to Markdown using the chosen strategy
        if strategy == 'markdownify':
            markdown_content = markdownify.markdownify(processed_html, heading_style="ATX")
        elif strategy == 'html2text':
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            markdown_content = h.handle(processed_html)
        else:
            raise ValueError(f"Unsupported preprocessing strategy: {strategy}")

        # Basic whitespace cleanup
        markdown_content = '\n'.join(line.strip() for line in markdown_content.splitlines() if line.strip())
        markdown_content = markdown_content.replace('\n\n\n', '\n\n') # Reduce excessive newlines

        # Truncate to max_length
        if len(markdown_content) > max_length:
            logger.warning(f"Truncating Markdown content from {len(markdown_content)} to {max_length} characters.")
            markdown_content = markdown_content[:max_length] + "... [Content truncated]"
            
        logger.info(f"HTML preprocessing completed. Output length: {len(markdown_content)}")
        return markdown_content

    except Exception as e:
        logger.error(f"Error during HTML preprocessing: {str(e)}", exc_info=True)
        raise PreprocessingError(f"Failed to preprocess HTML: {str(e)}") 