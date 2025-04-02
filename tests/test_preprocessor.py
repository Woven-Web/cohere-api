"""Tests for the preprocessor module."""

import pytest
from bs4 import BeautifulSoup
from app.core.preprocessor import preprocess_html, PreprocessingError

# Sample HTML content for testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <style>
        body { color: black; }
    </style>
    <script>
        console.log('test');
    </script>
</head>
<body>
    <nav>
        <a href="#home">Home</a>
    </nav>
    <div class="content">
        <h1>Welcome to Test Page</h1>
        <p>This is a test paragraph with a <a href="https://example.com">link</a>.</p>
        <!-- This is a comment -->
        <div class="ads">Advertisement content</div>
        <img src="test.jpg" alt="Test Image" data-custom="remove-me">
    </div>
    <footer>
        <p>Footer content</p>
    </footer>
</body>
</html>
"""

def test_basic_preprocessing():
    """Test basic HTML to Markdown conversion."""
    result = preprocess_html(SAMPLE_HTML)
    
    # Check that unwanted elements are removed
    assert "style" not in result.lower()
    assert "script" not in result.lower()
    assert "nav" not in result.lower()
    assert "footer" not in result.lower()
    
    # Check that desired content is preserved
    assert "Welcome to Test Page" in result
    assert "test paragraph" in result
    assert "example.com" in result
    assert "Test Image" in result
    
    # Check that comments are removed
    assert "This is a comment" not in result

def test_preprocessing_strategies():
    """Test different preprocessing strategies."""
    # Test markdownify strategy
    markdownify_result = preprocess_html(SAMPLE_HTML, strategy='markdownify')
    assert "# Welcome to Test Page" in markdownify_result
    
    # Test html2text strategy
    html2text_result = preprocess_html(SAMPLE_HTML, strategy='html2text')
    assert "Welcome to Test Page" in html2text_result
    
    # Test invalid strategy
    with pytest.raises(PreprocessingError) as exc_info:
        preprocess_html(SAMPLE_HTML, strategy='invalid')
    assert "Unsupported preprocessing strategy" in str(exc_info.value)

def test_custom_element_removal():
    """Test removal of custom elements."""
    custom_remove = ['nav', 'footer']  # Remove navigation and footer only
    result = preprocess_html(SAMPLE_HTML, remove_elements=custom_remove)
    
    # Check that specified elements are removed
    assert "Home" not in result  # nav content
    assert "Footer content" not in result  # footer content
    
    # Check that other content is preserved
    assert "Welcome to Test Page" in result
    assert "test paragraph" in result
    assert "Test Image" in result

def test_selector_removal():
    """Test removal of elements by CSS selector."""
    selectors = ['.ads', 'img[data-custom]']
    result = preprocess_html(SAMPLE_HTML, remove_by_selector=selectors)
    
    # Check that elements matching selectors are removed
    assert "Advertisement content" not in result
    assert "Test Image" not in result
    
    # Check that other content is preserved
    assert "Welcome to Test Page" in result
    assert "test paragraph" in result

def test_max_length():
    """Test content truncation."""
    max_length = 50
    result = preprocess_html(SAMPLE_HTML, max_length=max_length)
    
    assert len(result) <= max_length + len("... [Content truncated]")
    assert result.endswith("... [Content truncated]")

def test_invalid_html():
    """Test handling of invalid HTML."""
    invalid_html = "<p>Unclosed paragraph<script>alert('test')</script>"
    
    # Should not raise an exception for malformed HTML
    result = preprocess_html(invalid_html)
    assert "Unclosed paragraph" in result
    assert "alert" not in result  # script tag should be removed

def test_empty_html():
    """Test handling of empty HTML."""
    result = preprocess_html("")
    assert result == ""

def test_no_body_tag():
    """Test handling of HTML without body tag."""
    html_no_body = "<div>Test content</div>"
    result = preprocess_html(html_no_body)
    assert "Test content" in result

def test_attribute_handling():
    """Test handling of HTML attributes."""
    html_with_attrs = """
    <div class="remove-me" id="test" data-custom="remove">
        <a href="https://example.com" title="Example" target="_blank">Link</a>
        <img src="test.jpg" alt="Test" width="100">
    </div>
    """
    result = preprocess_html(html_with_attrs)
    
    # Check that allowed attributes are preserved
    assert "https://example.com" in result
    assert "Test" in result  # alt text
    
    # Check that other attributes are removed
    soup = BeautifulSoup(html_with_attrs, 'html.parser')
    processed_soup = BeautifulSoup(result, 'html.parser')
    
    if processed_soup.find('a'):
        assert 'target' not in processed_soup.find('a').attrs
    if processed_soup.find('img'):
        assert 'width' not in processed_soup.find('img').attrs

def test_preprocessing_error():
    """Test error handling."""
    # Mock a situation that would cause BeautifulSoup to fail
    with pytest.raises(PreprocessingError) as exc_info:
        preprocess_html(None)
    assert "Failed to preprocess HTML" in str(exc_info.value)
