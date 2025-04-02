"""
Main application module for the Cohere Event Scraper API.
Handles application configuration, middleware setup, and route registration.
"""

import logging
import os
from typing import Dict, Any
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn
from app.api.routes import router
from app.api.models import ErrorResponse

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load configuration from environment variables
class Config:
    """Application configuration loaded from environment variables."""
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    RELOAD: bool = os.getenv("RELOAD", "False").lower() == "true"
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", "10485760"))  # 10MB

config = Config()

# Initialize FastAPI application
app = FastAPI(
    title="Cohere Event Scraper API",
    description="API for scraping event information from web pages using Google Gemini",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    logger.warning(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation error",
            details=str(exc)
        ).dict(),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            details=str(exc) if app.debug else "An unexpected error occurred"
        ).dict(),
    )

@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint returning API information."""
    return {
        "message": "Welcome to Cohere Event Scraper API",
        "version": app.version,
        "docs_url": "/api/docs"
    }

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for monitoring."""
    # In a production environment, you might want to check:
    # - Database connectivity
    # - External service health
    # - System resources
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event() -> None:
    """Handle application startup events."""
    logger.info("Starting up Cohere Event Scraper API")
    logger.info(f"Log level set to {config.LOG_LEVEL}")
    logger.info(f"CORS origins: {config.ALLOWED_ORIGINS}")
    
    # Initialize any required resources here
    # For example:
    # - Initialize database connections
    # - Set up caching
    # - Initialize external service clients

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Handle application shutdown events."""
    logger.info("Shutting down Cohere Event Scraper API")
    
    # Clean up any resources here
    # For example:
    # - Close database connections
    # - Clear caches
    # - Close external service clients

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.lower()
    ) 