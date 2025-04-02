from fastapi.testclient import TestClient
import pytest
from app.main import app
from app.api.models import ScrapeRequest, ScrapeResponse

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()

def test_scrape_request_validation():
    # Test minimal valid request
    valid_request = {
        "url": "https://example.com",
        "gemini_api_key": "fake_api_key_for_testing12345"
    }
    request_model = ScrapeRequest(**valid_request)
    assert str(request_model.url) == "https://example.com/"
    assert request_model.gemini_api_key == "fake_api_key_for_testing12345"
    assert request_model.use_playwright is False
    assert request_model.custom_instructions_text is None

    # Test full valid request
    full_request = {
        "url": "https://example.com",
        "gemini_api_key": "fake_api_key_for_testing12345",
        "use_playwright": True,
        "custom_instructions_text": "Extract only location details"
    }
    request_model = ScrapeRequest(**full_request)
    assert request_model.use_playwright is True
    assert request_model.custom_instructions_text == "Extract only location details"

    # Test invalid API key (should raise ValueError)
    with pytest.raises(ValueError):
        ScrapeRequest(url="https://example.com", gemini_api_key="short")

    # Test invalid URL (should raise ValueError)
    with pytest.raises(ValueError):
        ScrapeRequest(url="not-a-url", gemini_api_key="fake_api_key_for_testing12345")

def test_scrape_response_validation():
    # Test empty response
    empty_response = {}
    response_model = ScrapeResponse(**empty_response)
    assert response_model.title is None
    assert response_model.description is None
    assert response_model.start_datetime is None
    assert response_model.end_datetime is None
    assert response_model.location is None

    # Test full response
    full_response = {
        "title": "Test Event",
        "description": "Test Description",
        "start_datetime": "2023-07-15T10:00:00Z",
        "end_datetime": "2023-07-15T12:00:00Z",
        "location": "Test Location"
    }
    response_model = ScrapeResponse(**full_response)
    assert response_model.title == "Test Event"
    assert response_model.start_datetime == "2023-07-15T10:00:00Z"

    # Test datetime conversion
    alt_format_response = {
        "title": "Test Event",
        "start_datetime": "2023-07-15 10:00:00", 
        "end_datetime": "2023/07/15 12:00"
    }
    response_model = ScrapeResponse(**alt_format_response)
    assert "T10:00:00" in response_model.start_datetime
    assert "T12:00:00" in response_model.end_datetime
    
# These tests will be implemented later as the API is developed
@pytest.mark.skip(reason="API not fully implemented yet")
def test_scrape_endpoint():
    response = client.post(
        "/api/scrape",
        json={
            "url": "https://example.com",
            "gemini_api_key": "fake_api_key_for_testing12345",
            "use_playwright": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "title" in data 