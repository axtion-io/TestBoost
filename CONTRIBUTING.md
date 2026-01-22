# Contributing to TestBoost

Thank you for your interest in contributing to TestBoost! We welcome contributions from the community.

## How to Contribute

### Simple Process: Fork → PR

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/TestBoost.git
   cd TestBoost
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** and commit them:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```
5. **Push** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. **Open a Pull Request** on the main repository

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install poetry
poetry install

# Copy environment config
cp .env.example .env

# Start PostgreSQL (optional - for integration tests)
docker-compose up -d postgres

# Run tests
pytest tests/
```

## Code Style

We use automated tools to maintain code quality:

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type check
mypy src/
```

Please ensure these pass before submitting your PR.

## Pull Request Guidelines

- Keep changes focused and atomic
- Write clear commit messages
- Update documentation if needed
- Add tests for new functionality
- Ensure all tests pass

## Questions?

If you have questions, feel free to:
- Open an issue for bugs or feature requests
- Start a discussion for general questions

## License

By contributing to TestBoost, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

---

Thank you for helping make TestBoost better!
