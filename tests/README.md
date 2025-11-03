# DonationFlow CLI Test Suite

This directory contains the comprehensive test suite for the cdflow-cli project.

## Test Structure

```
tests/
├── conftest.py                 # Pytest configuration and shared fixtures
├── pytest.ini                 # Pytest settings (moved to project root)
├── test_runner.py             # Test runner script
├── README.md                  # This file
│
├── unit/                      # Unit tests
│   ├── cli/                   # CLI command tests
│   │   ├── test_main.py
│   │   ├── test_commands_init.py
│   │   ├── test_commands_import.py
│   │   └── test_commands_rollback.py
│   │
│   ├── services/              # Service layer tests
│   │   ├── test_import_service.py
│   │   ├── test_rollback_service.py
│   │   └── test_auth_service.py
│   │
│   ├── adapters/              # Adapter tests
│   │   ├── test_canadahelps_parser.py
│   │   ├── test_paypal_parser.py
│   │   └── test_nationbuilder_client.py
│   │
│   └── utils/                 # Utility tests
│       └── test_config.py
│
├── integration/               # Integration tests
│   ├── test_cli_workflows.py
│   └── test_data_processing.py
│
└── fixtures/                  # Test data and fixtures
    ├── sample_data.py
    └── __init__.py
```

## Running Tests

### Quick Start

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/unit/cli/test_main.py

# Run tests matching a pattern
python -m pytest -k "test_init"
```

### Using the Test Runner

```bash
# Run all tests
python tests/test_runner.py

# Run only unit tests
python tests/test_runner.py unit

# Run only integration tests
python tests/test_runner.py integration

# Run with coverage report
python tests/test_runner.py --coverage

# Run with verbose output
python tests/test_runner.py --verbose
```

### Test Categories

Tests are organized into several categories using pytest markers:

- `unit`: Fast, isolated unit tests
- `integration`: Tests that involve multiple components
- `manual`: Tests that require manual setup or verification
- `slow`: Long-running tests

```bash
# Run only unit tests
python -m pytest -m unit

# Run only integration tests
python -m pytest -m integration

# Skip slow tests
python -m pytest -m "not slow"

# Run specific markers
python -m pytest -m "unit and not slow"
```

## Test Configuration

### Pytest Configuration

The test suite uses the following pytest configuration (in `pytest.ini`):

- **Test Discovery**: Automatically finds `test_*.py` files
- **Markers**: Strict marker enforcement to prevent typos
- **Warnings**: Filters out common deprecation warnings
- **Output**: Verbose output with short traceback format

### Fixtures

Common fixtures are defined in `conftest.py`:

- `temp_dir`: Temporary directory for test files
- `sample_config`: Sample configuration dictionary
- `sample_canadahelps_data`: Sample CSV data for CanadaHelps
- `sample_paypal_data`: Sample CSV data for PayPal
- `mock_nationbuilder_client`: Mock NationBuilder API client

## Writing Tests

### Unit Test Guidelines

1. **Isolation**: Each test should be independent
2. **Mocking**: Mock external dependencies (APIs, file system, etc.)
3. **Coverage**: Aim for high code coverage
4. **Naming**: Use descriptive test names that explain what is being tested

Example unit test:
```python
def test_validate_config_missing_slug(self, mock_config_provider):
    """Test config validation fails when slug is missing."""
    mock_config_provider.get_nationbuilder_config.return_value = {
        # Missing 'slug' field
        'client_id': 'test-id'
    }
    
    with pytest.raises(ValueError, match="slug is required"):
        service = MyService(config_provider=mock_config_provider)
        service.validate_config()
```

### Integration Test Guidelines

1. **Real Workflows**: Test actual command-line workflows
2. **Minimal Mocking**: Only mock external services, not internal logic
3. **Data Processing**: Test complete data processing pipelines
4. **Error Handling**: Test error scenarios and recovery

Example integration test:
```python
def test_import_command_workflow(self, temp_workspace, sample_config_file):
    """Test complete import command workflow."""
    result = subprocess.run([
        'python', '-m', 'cdflow_cli.cli.main',
        'import', '--config', str(sample_config_file)
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert 'success' in result.stdout.lower()
```

### Test Data

Use the fixtures in `tests/fixtures/sample_data.py` for consistent test data:

```python
from tests.fixtures.sample_data import SAMPLE_CANADAHELPS_CSV, SAMPLE_CONFIG

def test_with_sample_data(self, temp_dir):
    csv_file = temp_dir / 'test.csv'
    csv_file.write_text(SAMPLE_CANADAHELPS_CSV)
    # ... rest of test
```

## Coverage Reports

Generate coverage reports to ensure comprehensive testing:

```bash
# Generate HTML coverage report
python -m pytest --cov=cdflow_cli --cov-report=html

# Generate terminal coverage report
python -m pytest --cov=cdflow_cli --cov-report=term-missing

# Fail if coverage is below 80%
python -m pytest --cov=cdflow_cli --cov-fail-under=80
```

The HTML coverage report will be generated in `htmlcov/index.html`.

## Continuous Integration

These tests are designed to run in CI/CD environments:

```bash
# CI-friendly test run
python -m pytest --tb=short --strict-markers -x
```

## Debugging Tests

### Running Individual Tests

```bash
# Run a specific test method
python -m pytest tests/unit/cli/test_main.py::TestMainCLI::test_version_flag

# Run with debugging output
python -m pytest -s tests/unit/cli/test_main.py

# Drop into debugger on failures
python -m pytest --pdb tests/unit/cli/test_main.py
```

### Test Output

Use the `-v` flag for verbose output and `-s` to see print statements:

```bash
python -m pytest -v -s tests/unit/cli/test_main.py
```

## Best Practices

1. **Test Names**: Use descriptive names that explain the scenario
2. **One Assertion**: Focus on one behavior per test
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Mock External Dependencies**: Don't make real API calls in tests
5. **Use Fixtures**: Reuse common setup code
6. **Test Edge Cases**: Include error conditions and boundary cases
7. **Keep Tests Fast**: Unit tests should complete quickly
8. **Document Complex Tests**: Add docstrings for complex test scenarios

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure the project is installed in development mode:
   ```bash
   pip install -e .
   ```

2. **Missing Dependencies**: Install test dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Path Issues**: Run tests from the project root directory

4. **Mock Issues**: Ensure mocks are patched correctly and reset between tests

### Getting Help

- Check the test output for detailed error messages
- Use `-v` flag for verbose output
- Add print statements or use debugger for complex issues
- Review similar tests for patterns and examples