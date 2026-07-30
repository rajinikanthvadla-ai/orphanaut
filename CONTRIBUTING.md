# Contributing to Orphanaut

Thank you for your interest in contributing! Orphanaut is an educational tool to help students find and clean up billable AWS resources.

## Getting Started

1. Fork the repository and clone it locally.
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   .venv\Scripts\activate      # Windows
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Run the app:
   ```bash
   orphanaut
   # or
   python -m orphanaut
   ```

## Development

- **Lint:** `ruff check src tests`
- **Test:** `pytest -v`
- **Build locally:** `pyinstaller orphanaut.spec --noconfirm`

## Adding a New Resource Scanner

1. Create a scanner in `src/orphanaut/scanners/` extending `BaseScanner`.
2. Register it in `src/orphanaut/scanners/registry.py`.
3. Add a delete handler in `src/orphanaut/actions/deleter.py` if deletion should be supported.
4. Add tests where practical.

## Pull Requests

- Keep changes focused and well-described.
- Ensure CI passes (`ruff` + `pytest`).
- Do not commit AWS credentials or `.env` files.

## Code of Conduct

Be respectful and constructive. This project is used in educational settings.
