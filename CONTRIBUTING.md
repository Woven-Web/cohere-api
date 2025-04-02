# Contributing to Cohere Event Scraper API

Thank you for your interest in contributing to the Cohere Event Scraper API! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please read it before contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/cohere-event-scraper.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Push to your fork: `git push origin feature/your-feature-name`
6. Submit a pull request

## Development Environment

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

## Code Quality Standards

### Code Style

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use isort for import sorting
- Maximum line length: 88 characters (Black default)
- Use meaningful variable and function names
- Add docstrings to all functions and classes

### Type Hints

- Use type hints for all function parameters and return values
- Run MyPy to check type annotations

### Testing

- Write unit tests for all new functionality
- Maintain or improve code coverage
- Tests should be in the `tests/` directory
- Name test files with `test_` prefix
- Use pytest fixtures and parametrize when appropriate

### Documentation

- Update docstrings for modified code
- Update README.md if adding new features
- Add comments for complex logic
- Keep API documentation up to date

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the documentation if you're changing functionality
3. Add tests for new features
4. Ensure all tests pass and code quality checks succeed
5. Update the version numbers following [Semantic Versioning](https://semver.org/)
6. The PR will be merged once you have the sign-off of at least one maintainer

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes (formatting, etc.)
- refactor: Code refactoring
- test: Adding or modifying tests
- chore: Maintenance tasks

Example:
```
feat(api): add rate limiting to scrape endpoint

- Add rate limiting middleware
- Configure limits in environment variables
- Add tests for rate limiting
```

## Branch Strategy

- `main`: Production-ready code
- `develop`: Development branch
- Feature branches: `feature/your-feature`
- Bug fix branches: `fix/bug-description`
- Release branches: `release/vX.Y.Z`

## Setting Up Development Environment

### Required Tools

- Python 3.9+
- Docker and Docker Compose
- Git
- Your favorite IDE (VS Code recommended)

### VS Code Configuration

Recommended extensions:
- Python
- Docker
- YAML
- Black Formatter
- isort
- GitLens

### Environment Variables

Copy `.env.example` to `.env` and set the required variables:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_specific.py

# Run with verbose output
pytest -v
```

## Questions or Problems?

- Check existing issues
- Open a new issue with a clear description
- Tag with appropriate labels
- Include relevant code snippets and error messages

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License. 