# JobTrace

[![CI](https://github.com/mr-anjaneyam/JobTrace/actions/workflows/ci.yml/badge.svg)](https://github.com/mr-anjaneyam/JobTrace/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

**Self-hosted job tracker that watches company career portals, scores openings against your resume, and alerts you on Telegram.**

JobTrace polls applicant tracking systems directly, diffs postings against a local SQLite database, scores each new opening with an LLM (or a free offline matcher), and sends you a short Telegram message when something relevant appears. A React dashboard lets you browse and search everything it found.

## Features

- **Direct ATS integration:** Greenhouse, Lever, Ashby, Workable, Workday, Oracle Recruiting Cloud and Atlassian, plus the Remotive and Arbeitnow feeds.
- **Telegram alerts and weekly digests:** no SMTP setup, messages are HTML-escaped and split to fit Telegram's 4096 character limit.
- **Stateful tracking:** every fetched job is stored, so a posting that fails your filters is never reported as "closed" by mistake. Roles that disappear from a board are marked closed.
- **Stable job IDs:** tracking parameters (`utm_*`, `gh_src`, `lever-source`, ...) are stripped before hashing.
- **Seniority, location and relevance gates:** intern, junior, mid, senior, lead or any. Mismatched roles are capped in code, without spending tokens.
- **Token budget controls:** batch scoring (up to 25 jobs per request), an optional free local triage, and a daily token limit.
- **Pluggable scoring:** xkiro, OpenAI, OpenRouter, Ollama, Cursor, JEV, a built-in offline matcher, or none.
- **Web dashboard:** opportunity map, match matrix, job detail, compare view, FTS5 full-text search, live scan progress over Server-Sent Events, resume upload and settings.
- **Cross-platform:** Windows (PowerShell), macOS and Linux.

See [OVERVIEW.md](OVERVIEW.md) for the architecture, database schema and design notes.

## Quick start

Requirements: Python 3.10+ and Node.js 18+.

```bash
git clone https://github.com/mr-anjaneyam/JobTrace.git
cd JobTrace

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Local config (both files are git-ignored)
cp config.example.yaml config.yaml
cp .env.example .env
```

`./install.sh` does the same on macOS and Linux, inside a virtualenv.

Start the backend and the dashboard together:

```powershell
# Windows
.\start.ps1        # or start.bat
```
```bash
# macOS / Linux
./start.sh
```

Then open <http://localhost:3000>. The API listens on <http://127.0.0.1:8000> (interactive docs at `/docs`). `stop.ps1` / `stop.sh` shut everything down.

## Configuration

1. **Telegram:** create a bot with [@BotFather](https://t.me/BotFather), message it once, then find your chat ID via [@userinfobot](https://t.me/userinfobot). Enter both in the dashboard under Settings, or set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. Multiple chat IDs are supported.
2. **Resume:** upload a PDF, DOCX, TXT or MD file in the dashboard (Candidate Profile), or set `resume_path` in `config.yaml`.
3. **Scoring provider:** set `llm.provider` in `config.yaml` and the matching key in `.env` (see [.env.example](.env.example)). Use `local` for free offline matching or `none` to skip scoring.
4. **Companies and filters:** edit `companies`, `filters`, `candidate` and `alerts` in `config.yaml`. [config.example.yaml](config.example.yaml) documents every option.

Secrets live only in `.env` and `config.yaml`, both ignored by git. The settings API never returns full secrets, only a masked tail.

### Performance on low-end machines

The dashboard switches to a lite mode automatically on devices with 4 or fewer CPU cores, 4 GB or less memory, or reduced-motion enabled. Lite mode drops shadows, animations, the background grid and quadrant tints, and shows up to 80 map pins instead of 150. Force a mode from the browser console and reload:

```js
localStorage.setItem('jobtrace.perf', 'lite');   // or 'full'; removeItem to go back to auto
```

## Command line

Run from the `backend/` directory (Windows users can use `.\run.ps1 <command>` from the repo root):

```bash
python -m jobtrace.main scan             # fetch, diff and score
python -m jobtrace.main alert            # Telegram alert for watched companies
python -m jobtrace.main digest           # weekly digest
python -m jobtrace.main run              # scan + digest
python -m jobtrace.main recap            # re-apply seniority/relevance caps (0 tokens)
python -m jobtrace.main list --days 7    # recent openings in the terminal
python -m jobtrace.main test             # verify Telegram credentials
python -m jobtrace.main web --port 8000  # API server only
python -m jobtrace.main daemon           # built-in scheduler
```

`alert` and `digest` accept `--dry-run` to preview without sending.

### Scheduling

`daemon` runs a daily alert pass at 09:30 and a weekly digest (scan first) on Mondays at 09:00, catching up if it starts late. You can also schedule `alert` and `run` with cron, Task Scheduler or systemd timers.

### Network exposure

The API binds to `127.0.0.1` by default and has no authentication. Set `JOBTRACE_HOST` only if you understand the risk, and never expose it to the internet without a reverse proxy that adds authentication. The dev server started by `start.ps1` / `start.sh` listens on all interfaces; remove `--host 0.0.0.0` there if you do not want other devices on your network to reach the dashboard.

## Development

```bash
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest          # backend tests (use a temporary project root)
cd frontend && npx tsc --noEmit         # type-check
cd frontend && npm run build            # production build
```

```
JobTrace/
├── backend/
│   ├── jobtrace/        # Python package: pipeline, sources, store, scoring, Telegram, scheduler
│   │   └── web/         # FastAPI server
│   └── tests/           # pytest suite
├── frontend/            # React 19 + Vite + Tailwind dashboard
├── config.example.yaml  # configuration template
├── .env.example         # secrets template
├── start.* / stop.*     # full-stack launchers (PowerShell, bash, batch)
└── run.ps1              # Windows CLI wrapper
```

## Contributing

Bug reports, feature ideas and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) first. Report security issues privately as described in [SECURITY.md](SECURITY.md).

Good first contributions: a new ATS adapter in `backend/jobtrace/sources.py`, a new scoring provider in `backend/jobtrace/llm.py`, or more tests.

## License

MIT. See [LICENSE](LICENSE).
