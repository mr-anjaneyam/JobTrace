# Contributing to JobTrace

Thanks for helping out. This guide keeps contributions quick to review.

## Ground rules

- Be kind. Everyone must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Search [existing issues](https://github.com/mr-anjaneyam/JobTrace/issues) before opening a new one.
- For anything larger than a small fix, open an issue first so we can agree on the approach.
- Never commit secrets, resumes, `config.yaml`, `.env` or database files. They are git-ignored; keep it that way.

## Set up

```bash
git clone https://github.com/<your-user>/JobTrace.git
cd JobTrace
pip install -r backend/requirements-dev.txt
cd frontend && npm install
```

Copy `config.example.yaml` to `config.yaml` and `.env.example` to `.env` to run the app locally. Use `./start.sh` or `.\start.ps1` to launch both servers.

## Before you open a pull request

```bash
cd backend && python -m pytest
cd ../frontend && npx tsc --noEmit && npm run build
```

All three must pass; CI runs the same checks.

- **Tests:** add or update tests for behaviour changes. Tests must never touch your real `config.yaml`, `.env` or database. Use the `workspace` fixture in `backend/tests/conftest.py` for anything that reads or writes project files, and temporary databases for the store.
- **Backend style:** Python 3.10+, type hints on new public functions, short comments only where the code cannot explain itself.
- **Frontend style:** TypeScript with no `any` in new code where a real type exists, Tailwind utility classes, and no new dependency without a reason.
- **Scope:** one logical change per pull request. Do not mix refactors with fixes.
- **Punctuation:** do not use em dashes or en dashes in code, comments, docs or UI text. Use a hyphen, colon or rephrase.

## Commit messages

Use short imperative subjects, optionally with a prefix such as `feat:`, `fix:`, `docs:`, `test:` or `chore:`.

## Adding an ATS source

1. Add a function in `backend/jobtrace/sources.py` with the signature `fn(name, slug) -> list[dict]` that returns jobs built with the `_norm` helper.
2. Register it in the `BOARDS` dict under a new `board` name.
3. Add a test in `backend/tests/test_sources.py` that parses a sample payload (no live network calls in tests).
4. Document the board and its `slug` format in `config.example.yaml`.

## Adding a scoring provider

OpenAI-compatible endpoints only need an entry in `ENDPOINTS` in `backend/jobtrace/llm.py`. Anything else should expose a scorer with `score_batch(profile, jobs)` returning `{job_id: (score, reason, breakdown)}` and be wired up in `make_scorer`.

## Reporting security problems

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
