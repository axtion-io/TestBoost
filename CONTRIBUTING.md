# Contributing to TestBoost

Thank you for your interest in contributing to TestBoost! We welcome contributions from the community.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/axtion-io/TestBoost/issues)
2. If not, create a new issue using the bug report template
3. Include as much detail as possible: steps to reproduce, expected vs actual behavior, environment details

### Suggesting Features

1. Check existing [Issues](https://github.com/axtion-io/TestBoost/issues) for similar suggestions
2. Create a new issue using the feature request template
3. Describe the use case and why this feature would be valuable

### Submitting Code

1. **Fork** the repository
2. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** with clear, focused commits
4. **Run tests** and code quality checks:
   ```bash
   pytest tests/
   ruff check src/
   black src/
   mypy src/
   ```
5. **Push** your branch and create a Pull Request

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/TestBoost.git
cd TestBoost

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install poetry
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Start database
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Run tests
pytest tests/
```

## Code Style

- **Python**: Follow PEP 8, enforced by `ruff` and `black`
- **Type hints**: Use type annotations, checked by `mypy`
- **Tests**: Add tests for new functionality
- **Commits**: Use clear, descriptive commit messages

## Pull Request Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Ensure all tests pass
- Be responsive to review feedback

## Code of Conduct

Be respectful and constructive. We're all here to build something great together.

## Questions?

Feel free to open an issue for any questions about contributing.

## License

By contributing to TestBoost, you agree that your contributions will be licensed under the Apache License 2.0.
