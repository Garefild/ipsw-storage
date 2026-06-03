# Contributing

## Setup

Use Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```bash
python -m ruff check .
python -m pytest
python -m build
```

## Pull Requests

Keep changes focused, include tests for behavior changes, and update the README
when CLI behavior or packaging changes.

## Releases

Releases are published by the GitHub Actions release workflow when a GitHub
release is published. Package metadata should be updated before tagging.
