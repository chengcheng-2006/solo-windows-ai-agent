# Contributing to Solo

We welcome contributions! Here's how you can help.

## Code of Conduct

This project follows a Contributor Code of Conduct. By participating, you agree to maintain a respectful, inclusive community.

## How to Contribute

### Reporting Bugs
1. Check existing Issues to avoid duplicates
2. Use the Bug Report template
3. Include:
   - Windows version
   - Solo version (commit hash)
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable
   - Relevant logs (with secrets redacted)

### Suggesting Features
1. Check existing Issues and Roadmap
2. Use the Feature Request template
3. Describe the use case and desired behavior
4. Note any security or safety considerations

### Pull Requests

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/my-feature`
3. **Make your changes**
4. **Write or update tests**
5. **Run the test suite**: `.\tests\run_all.ps1`
6. **Commit** with conventional commit messages
7. **Push** to your fork
8. **Submit a PR** against the `main` branch

### PR Requirements
- Pass CI checks (lint, tests, secret scan)
- Include tests for new functionality
- Update documentation as needed
- No secrets or credentials in the code
- New high-risk actions must include approval gates
- New Computer Use capabilities must include safety tests

## Development Setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed setup instructions.

## Code Style

- Python: PEP 8, type hints, max line length 100
- PowerShell: PSScriptAnalyzer rules
- Markdown: Keep lines under 80 chars
- Commits: Conventional Commits format

## Testing

```powershell
# Run all tests
.\tests\run_all.ps1

# Run smoke tests only
.\tests\run.ps1 -Suite smoke

# Run Python unit tests
pytest
```

## Documentation

- Update relevant docs when changing behavior
- Keep README examples working
- Use clear, concise language
- Include code examples where helpful

## Questions?

Open a Discussion or ask in the Issues section.
