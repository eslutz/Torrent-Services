# Contributing to Torrent Services

Thank you for your interest in contributing to Torrent Services! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose
- Git

### Setting Up Your Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/eslutz/Torrent-Services.git
   cd Torrent-Services
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   playwright install chromium
   ```

3. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Running Tests

We use pytest for testing. All tests are located in the `tests/` directory.

### Run All Tests

```bash
pytest tests/
```

### Run Tests with Coverage

```bash
pytest tests/ --cov=scripts --cov-report=html --cov-report=term-missing
```

This generates a coverage report in `htmlcov/index.html`.

### Run Specific Tests

```bash
# Run tests for a specific module
pytest tests/setup/test_common.py

# Run a specific test
pytest tests/setup/test_common.py::TestLoadConfig::test_load_config_success
```

### Run Tests in Verbose Mode

```bash
pytest tests/ -v
```

## Code Quality

### Linting

We use pylint and black for code quality:

```bash
# Check code formatting
black --check scripts/ tests/

# Format code
black scripts/ tests/

# Run pylint
pylint scripts/setup/*.py
```

### Type Checking

While not strictly enforced, consider using type hints in your code.

## Testing Guidelines

### Writing Tests

1. **Test file naming**: Test files should be named `test_*.py`
2. **Test class naming**: Test classes should be named `Test*`
3. **Test function naming**: Test functions should be named `test_*`

### Test Structure

```python
def test_function_name():
    """Test description explaining what is being tested"""
    # Arrange - Set up test data and conditions
    
    # Act - Execute the code being tested
    
    # Assert - Verify the results
```

### Mocking External Dependencies

When testing functions that make HTTP requests or interact with external services, use the `responses` library or `pytest-mock`:

```python
import responses

@responses.activate
def test_api_call():
    responses.add(
        responses.GET,
        "http://localhost:8989/api/v3/system/status",
        json={"status": "ok"},
        status=200
    )
    # Test code here
```

### Test Coverage

- Aim for at least 80% code coverage for new code
- Write tests for both success and failure scenarios
- Test edge cases and error handling

## Shell Script Testing

Shell scripts (healthchecks) should be tested for:
- Syntax errors (using shellcheck)
- Exit codes
- Error handling

Run shellcheck on modified scripts:
```bash
shellcheck scripts/healthchecks/*.sh
```

## CI/CD Pipeline

All pull requests trigger the CI/CD pipeline which runs:
- **Python tests**: pytest with coverage reporting
- **Linting**: black and pylint checks
- **Shell linting**: shellcheck on all shell scripts
- **Security analysis**: CodeQL static analysis

The pipeline must pass before a PR can be merged.

## Pull Request Process

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit them:
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

3. **Run tests locally** before pushing:
   ```bash
   pytest tests/
   black --check scripts/ tests/
   ```

4. **Push your branch** and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Wait for CI/CD checks** to pass

6. **Respond to review feedback** if any

## Code Style

- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Add comments for complex logic

## Commit Messages

- Use clear, descriptive commit messages
- Start with a verb in present tense (e.g., "Add", "Fix", "Update")
- Keep the first line under 72 characters
- Add detailed description if needed

Example:
```
Add retry logic to wait_for_service function

- Implement exponential backoff
- Add detailed error logging
- Include timeout parameter
```

## Questions or Issues?

If you have questions or run into issues:
- Check existing issues on GitHub
- Create a new issue with detailed information
- Reach out to maintainers

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.
