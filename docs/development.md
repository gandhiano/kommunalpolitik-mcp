# Development Workflow

This project uses a small branch-and-PR workflow so `main` stays stable and deployable.

## Branches

- Keep `main` stable.
- Do not develop directly on `main` except for urgent repository maintenance.
- Create short-lived branches from an up-to-date `main`.
- Use branch names like `feat/config-driven-ingestion`, `fix/document-search`, `docs/hosted-mcp-plan`, or `chore/package-cli`.

## Commits

- Use concise conventional-style commit subjects.
- Prefer `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, and `chore:`.
- Keep commits focused on one logical change.
- Do not commit local data, downloaded PDFs, SQLite databases, credentials, or private MCP configs.

## Pull Requests

- Open a PR for each branch, even when working solo.
- Keep the PR scope small enough to review from the diff.
- Include verification notes in the PR body.
- Merge only after the relevant checks or manual smoke tests pass.

## Baseline Verification

Run these before merging changes that touch Python code or MCP behavior:

```bash
.venv/bin/python -m compileall src
```

For local Witzenhausen data changes or runtime config changes:

```bash
KOMMUNALPOLITIK_DB_PATH=data/witzenhausen/witzenhausen.sqlite \
  .venv/bin/python -m src.ingest.witzenhausen status
```

For MCP tool changes, run a stdio smoke test or check the configured client can list and call the tools.

## Current Next Milestones

- Config-driven Witzenhausen ingestion via `configs/municipalities/witzenhausen.json`.
- Python package/CLI setup.
- Docker and hosted HTTP MCP transport.
