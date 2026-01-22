## Description

<!-- Provide a clear and concise description of your changes -->

## Related Issues

<!-- Link any related issues using "Fixes #123" or "Relates to #456" -->

- Fixes #
- Relates to #

## Type of Change

Please check the type(s) that apply:

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Refactoring (code improvement without changing functionality)
- [ ] Documentation update
- [ ] CI/CD or build configuration
- [ ] Dependencies update

## Component Affected

Which component(s) does this PR modify?

- [ ] API Server (`src/api/`)
- [ ] CLI (`src/cli/`)
- [ ] LangGraph Workflows (`src/core/langgraph/`)
- [ ] DeepAgents Integration (`src/core/agents/`)
- [ ] Database / Models (`src/db/`)
- [ ] MCP Server
- [ ] Documentation
- [ ] CI/CD / GitHub Actions
- [ ] Tests
- [ ] Other: ___

## Testing

### Tests Performed

<!-- Describe the tests you ran to verify your changes -->

- [ ] Unit tests pass (`pytest tests/unit/ -v`)
- [ ] Integration tests pass (`pytest tests/integration/ -v`)
- [ ] New tests added for new functionality
- [ ] Manual testing performed

### Test Commands Used

```bash
# Add the commands you used to test
poetry run pytest tests/ -v
poetry run ruff check .
poetry run mypy src/
```

## Checklist

Before submitting, please confirm:

- [ ] My code follows the project's code style (Ruff, mypy)
- [ ] I have run `ruff check .` and fixed any issues
- [ ] I have run `mypy src/` with no new type errors
- [ ] I have added/updated tests for my changes
- [ ] All new and existing tests pass locally
- [ ] I have updated documentation if needed
- [ ] I have removed any sensitive data (API keys, passwords)
- [ ] My commits have clear, descriptive messages
- [ ] I have rebased on the latest `main` or `develop` branch

## Screenshots (if applicable)

<!-- Add screenshots for UI changes or visual output -->

## Additional Notes

<!-- Any additional information reviewers should know -->

---

### For Maintainers

- [ ] Code review completed
- [ ] CI checks passing
- [ ] Documentation reviewed (if applicable)
- [ ] Ready to merge
