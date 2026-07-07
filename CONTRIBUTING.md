# Contributing to Blood Report Analyser

Thanks for your interest in contributing! This project is a RAG-powered blood report analysis app — see the [README](README.md) for the architecture and stack.

## Getting started

1. Fork the repo and clone your fork
2. Follow the **Local setup** section in the [README](README.md#local-setup) — you'll need free-tier accounts for Groq, Supabase, Qdrant, and LangSmith
3. Verify your setup: `python scripts/smoke_test.py`

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests are unit-level and run without any API keys or real patient data. Please add tests for any new extraction logic or parsing behavior.

## Branch and commit conventions

- Branch names: `feature/...`, `fix/...`, `refactor/...`, `chore/...`
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/): `feat(scope): description`, `fix(scope): description`, etc.
- Open a pull request against `main` — PRs are squash-merged

## What to work on

- Check [good first issues](https://github.com/shreyanshverma7/blood-report-analyser/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) for curated starter tasks
- Adding support for a new lab's report format is a great self-contained contribution — see `src/ingestion/marker_extractor.py` for the pattern

## Important: no real patient data

Never commit real blood report PDFs or any personally identifiable health data — not in code, tests, fixtures, or issues. Use synthetic data only. The `.gitignore` blocks `*.pdf` for this reason.

## Questions?

Open a [Discussion](https://github.com/shreyanshverma7/blood-report-analyser/discussions) — happy to help you get unblocked.
