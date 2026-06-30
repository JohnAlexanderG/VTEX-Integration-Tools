# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

This repository is a collection of Python utilities for VTEX e-commerce integrations. Most tools are organized as numbered workflow steps that transform catalog data, enrich it with VTEX identifiers, create products/SKUs, upload media, and update prices or inventory.

The root `README.md` is the user-facing workflow reference. `CLAUDE.md` contains additional historical agent guidance. Keep this file aligned with both when changing project conventions.

## Repository Layout

- `01_csv_to_json/` through numbered folders: sequential data-processing and VTEX API workflow steps.
- Utility folders such as `json_to_csv/`, `json_to_ndjson/`, `translate_keys/`, `to_dynamojson/`, and `generate_sale_xml/`: standalone conversion or export helpers.
- `webapp/backend/`: FastAPI backend and templates for the web UI.
- `webapp/frontend/`: Vite/React frontend source.
- `.env.example`: example VTEX/API environment variables. Never commit real credentials.

## Environment

- Primary runtime: Python 3.
- Typical setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install requests python-dotenv
```

- The web backend dependencies are listed in `webapp/backend/requirements.txt`.
- Many root scripts infer dependencies from imports instead of using a single top-level requirements file.
- VTEX API scripts expect a root `.env` with:
  - `X-VTEX-API-AppKey`
  - `X-VTEX-API-AppToken`
  - `VTEX_ACCOUNT_NAME`
  - `VTEX_ENVIRONMENT`

## Common Commands

- Get script usage before changing invocation behavior:

```bash
python3 path/to/script.py --help
```

- Run a single Python utility:

```bash
python3 01_csv_to_json/csv_to_json.py input.csv output.json --indent 4
```

- Validate JSON output:

```bash
python3 -m json.tool output.json >/dev/null
```

- Install backend dependencies:

```bash
pip install -r webapp/backend/requirements.txt
```

## Coding Guidelines

- Prefer small, focused changes in the script or workflow step being modified.
- Preserve command-line interfaces unless the task explicitly requires changing them.
- Keep CSV/JSON handling explicit about encoding; UTF-8 is the expected default.
- Use 4-space JSON indentation when writing human-reviewed workflow artifacts.
- Maintain the existing pattern of clear terminal progress output, detailed error reporting, and timestamped reports where already present.
- Use `requests` and `python-dotenv` consistently for VTEX API scripts unless a local module already provides a better project-specific helper.
- Keep rate limiting, retry behavior, and dry-run support intact for VTEX API operations.
- Do not introduce broad framework changes across the numbered scripts without a specific migration request.

## Data And Credentials

- Treat `.env`, VTEX credentials, API tokens, customer exports, generated CSV/JSON/NDJSON, and spreadsheet files as sensitive local data.
- Do not commit generated workflow outputs unless the user explicitly asks for sample fixtures.
- The root `.gitignore` intentionally excludes most generated data files.
- When adding tests or examples, prefer small synthetic fixtures that do not expose real VTEX catalog data.

## VTEX API Safety

- For scripts that mutate VTEX state, preserve or add `--dry-run` behavior when practical.
- Be careful with deletion, price updates, inventory resets, SKU creation, image uploads, and category creation.
- Confirm whether an operation is intended to hit live VTEX APIs before running it.
- Avoid running scripts that require real credentials unless the user explicitly asks.

## Testing And Validation

- There is no single global test suite for all tools.
- For narrow script changes, prefer targeted checks:
  - `python3 path/to/script.py --help`
  - small synthetic input/output run
  - `python3 -m json.tool` for JSON outputs
  - existing local tests such as `16_merge_sku_images/test_normalize_sku.py`
- For backend work, install `webapp/backend/requirements.txt` in a virtualenv and run focused FastAPI/import checks.
- For frontend work, inspect the available frontend package setup before assuming npm scripts exist.

## Documentation

- Each numbered tool should keep its local `README.md` accurate when behavior or arguments change.
- Update the root `README.md` for workflow-level changes.
- Keep examples executable and avoid placeholder credentials in committed commands.

## Git Hygiene

- The worktree may contain local generated data and untracked workflow folders.
- Do not delete or revert user changes unless explicitly asked.
- Keep unrelated files out of commits and patches.
- If a Markdown file should be committed, ensure it is allow-listed in `.gitignore`.
