# Cohere Event Scraper API

[![CI](https://github.com/yourusername/cohere-event-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/cohere-event-scraper/actions/workflows/ci.yml)
[![CD](https://github.com/yourusername/cohere-event-scraper/actions/workflows/cd.yml/badge.svg)](https://github.com/yourusername/cohere-event-scraper/actions/workflows/cd.yml)
[![Code Coverage](https://codecov.io/gh/yourusername/cohere-event-scraper/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/cohere-event-scraper)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A robust API for extracting structured event information from web pages using Google's Gemini LLM technology.

## Overview

This API provides a powerful solution for extracting event information (title, description, date/time, location) from web pages using a combination of advanced web scraping techniques and Google's Gemini LLM. It handles both simple static websites and complex JavaScript-rendered pages, making it suitable for a wide range of use cases.

## Key Features

- **Flexible Content Fetching**
  - Basic HTTP content fetching for static sites
  - Advanced browser-based scraping using Playwright for dynamic content
  - Configurable timeouts and retry mechanisms

- **Intelligent Processing**
  - Smart HTML preprocessing and cleaning
  - Markdown conversion for better LLM processing
  - Google Gemini LLM integration for accurate information extraction

- **Production-Ready Architecture**
  - FastAPI-based REST API with automatic validation
  - Comprehensive error handling and logging
  - Rate limiting and security features
  - Docker containerization with multi-stage builds
  - Health checks and monitoring
  - Configurable via environment variables

## Project Structure

```
.
├── app/                  # Main application code
│   ├── api/             # FastAPI routes and models
│   │   ├── models.py    # Pydantic models for validation
│   │   └── routes.py    # API endpoint definitions
│   ├── core/            # Core business logic
│   │   ├── fetchers.py  # Content fetching strategies
│   │   ├── llm.py      # Gemini LLM integration
│   │   └── parser.py    # Response parsing and validation
│   └── main.py         # Application entry point
├── tests/              # Test suite
│   ├── conftest.py    # Test configuration
│   ├── test_*.py      # Test modules
├── docker/            # Docker configuration
├── scripts/          # Utility scripts
├── .env.example      # Example environment variables
├── .env.prod.example # Production environment template
├── Dockerfile        # Development container
├── Dockerfile.prod   # Production container
├── docker-compose.yml # Container orchestration
├── requirements.txt   # Production dependencies
└── requirements-dev.txt # Development dependencies
```

## Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- Google Gemini API key

### Local Development

1. Clone and setup:
```bash
git clone https://github.com/yourusername/cohere-event-scraper.git
cd cohere-event-scraper
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run development server:
```bash
uvicorn app.main:app --reload
```

### Docker Development

```bash
# Start development environment
docker-compose up app-dev

# Run tests
docker-compose run --rm app-dev pytest

# Code quality checks
docker-compose run --rm app-dev pre-commit run --all-files
```

### Production Deployment

1. Configure production settings:
```bash
cp .env.prod.example .env.prod
# Edit .env.prod with production values
```

2. Deploy with Docker:
```bash
docker-compose -f docker-compose.yml up app-prod -d
```

## API Reference

### POST /api/scrape

Extract event information from a webpage.

#### Request

```json
{
  "url": "https://example.com/event-page",
  "gemini_api_key": "your_api_key",
  "use_playwright": false,
  "custom_instructions": "Optional instructions for the LLM",
  "timeout": 30000
}
```

#### Response

```json
{
  "title": "Sample Event Title",
  "description": "Detailed event description...",
  "start_datetime": "2024-07-15T10:00:00Z",
  "end_datetime": "2024-07-15T12:00:00Z",
  "location": "123 Main St, Example City",
  "metadata": {
    "confidence_score": 0.95,
    "extraction_method": "gemini_llm",
    "processing_time_ms": 1234
  }
}
```

#### Error Responses

```json
{
  "error": "error_type",
  "message": "Human-readable error message",
  "details": {
    "technical_details": "Additional error context",
    "request_id": "unique_request_identifier"
  }
}
```

Status codes:
- 400: Bad Request (invalid input)
- 401: Unauthorized (invalid API key)
- 422: Validation Error (malformed request)
- 429: Rate Limit Exceeded
- 500: Internal Server Error
- 503: Service Unavailable

## Security Best Practices

### API Key Management
- Store API keys in environment variables
- Rotate keys regularly
- Use separate keys for development/production
- Monitor key usage for suspicious activity

### Rate Limiting
- Per-client rate limits
- Configurable limits and windows
- IP-based and API key-based limiting
- Automatic blocking of abusive clients

### Input Validation
- Strict URL validation and sanitization
- Content size limits
- Content type verification
- Request payload validation

### Security Headers
- CORS configuration
- HTTPS enforcement
- Content Security Policy
- XSS Protection
- HSTS configuration

### Error Handling
- Sanitized error messages
- No sensitive data in responses
- Detailed internal logging
- Request tracing

## Monitoring

### Health Checks
- Endpoint: `/health`
- Checks:
  - API availability
  - Dependencies status
  - Resource usage
  - Response times

### Metrics
- Prometheus endpoint: `:9090/metrics`
- Key metrics:
  - Request rates and latencies
  - Error rates
  - Resource utilization
  - Cache hit rates

### Logging
- Structured JSON logging
- Configurable log levels
- Request/response logging
- Error tracking integration

## Troubleshooting Guide

### Common Issues

1. Rate Limiting
```
Issue: "Rate limit exceeded"
Solution:
- Check current rate limits in configuration
- Implement request batching
- Consider upgrading limits
```

2. Content Extraction
```
Issue: "Failed to extract content"
Solutions:
- Verify URL accessibility
- Check JavaScript rendering requirements
- Adjust timeout settings
- Validate HTML structure
```

3. LLM Processing
```
Issue: "LLM processing failed"
Solutions:
- Verify API key validity
- Check input content size
- Review content format
- Adjust retry settings
```

### Performance Optimization

1. Response Times
- Enable caching
- Optimize content fetching
- Configure timeouts
- Use connection pooling

2. Resource Usage
- Monitor memory usage
- Adjust worker counts
- Configure resource limits
- Implement request queuing

3. Error Rates
- Implement circuit breakers
- Add retry mechanisms
- Monitor error patterns
- Adjust validation rules

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Deployment

### Deploying to Render

This API is configured for easy deployment to Render using Docker. Follow these steps:

1. Fork or clone this repository to your GitHub account
2. Create a new Web Service on Render
3. Connect your GitHub repository
4. Select "Docker" as the environment
5. Choose the "starter" (free) or "standard" plan
6. Set the following environment variables in the Render dashboard:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - Other environment variables are automatically set via `render.yaml`

The service will automatically:
- Build using the production Dockerfile
- Run health checks at `/health`
- Scale with multiple workers
- Handle HTTPS and domain configuration

### Production Considerations

1. **Rate Limiting**: The API includes built-in rate limiting (100 requests per minute by default)
2. **Security**:
   - All endpoints use HTTPS
   - CORS is configured (update `ALLOWED_ORIGINS` for your domains)
   - Security headers are enabled
   - API key authentication can be enabled via `X-API-Key` header

3. **Performance**:
   - Uses multiple worker processes
   - Caches Playwright browser instances
   - Implements retry logic for failed requests
   - Optimized Docker image size

4. **Monitoring**:
   - Health check endpoint at `/health`
   - Prometheus metrics at `/metrics`
   - Detailed logging with configurable levels
   - Request tracing for debugging

5. **Scaling**:
   - Stateless design allows horizontal scaling
   - Configure `workers` count based on CPU cores
   - Adjust rate limits as needed
   - Monitor resource usage through Render dashboard

### Troubleshooting

Common deployment issues and solutions:

1. **Playwright Issues**:
   - Ensure browser dependencies are installed
   - Check browser cache permissions
   - Verify timeout settings

2. **Memory Usage**:
   - Monitor worker memory consumption
   - Adjust worker count if needed
   - Consider upgrading plan for more resources

3. **Rate Limiting**:
   - Check logs for rate limit errors
   - Adjust limits in environment variables
   - Implement client-side retry logic

4. **API Integration**:
   - Verify CORS settings
   - Check API key configuration
   - Monitor request/response patterns

For more detailed logs and metrics, check the Render dashboard or enable debug logging by setting `LOG_LEVEL=debug`.