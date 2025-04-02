from setuptools import setup, find_packages

setup(
    name="cohere-event-scraper",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.95.0",
        "uvicorn>=0.22.0",
        "requests>=2.31.0",
        "playwright>=1.40.0",
        "beautifulsoup4>=4.12.0",
        "html2text>=2024.2.16",
        "markdownify>=0.11.6",
        "google-generativeai>=0.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "black>=23.3.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "pre-commit>=3.3.2",
        ],
    },
    python_requires=">=3.9",
    author="Cohere",
    author_email="info@cohere.com",
    description="API for scraping event information from web pages using Google Gemini",
    keywords="scraper, api, gemini, events",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
) 