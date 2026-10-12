# JobTrace

> **Stateful career intelligence, LLM scoring, and instant Telegram alerts.**

JobTrace continuously monitors company career portals, diffs postings against a local database, scores matching openings against your resume using LLMs (or offline keyword matching), and delivers instant notifications and weekly digests directly to your **Telegram** chat.

---

## ⚡ What Makes JobTrace Different

- **Direct ATS Integration:** Scrapes 7 ATS platforms natively (**Greenhouse, Lever, Ashby, Workable, Workday, Oracle Recruiting Cloud, Atlassian**) plus remote aggregators (**Remotive, Arbeitnow**).
- **Instant Telegram Bot Alerts:** Replaces clunky email/SMTP setups with high-priority markdown/HTML cards in Telegram, formatted cleanly with direct application links.
- **Stateful Presence Tracking:** Jobs failing your initial filters are still presence-tracked, preventing false "job closed" events when filters change.
- **Deterministic ID Normalization:** Strips UTM and analytics query parameters (`utm_source`, `lever-source`, `gh_src`, etc.) so job IDs stay stable across scans.
- **Configurable Seniority Gate:** Tailored for *intern*, *junior*, *mid*, *senior*, or *lead* candidates. Automatically caps mismatching roles (e.g., senior director roles for a junior applicant) without consuming tokens.
- **Multi-Dimensional Relevance:** Evaluates skills, seniority, location, domain, recency, and reach. Irrelevant roles are capped even if they match keywords.
- **Token Economy & Budget Controls:** Supports token budgets, local triage floors (score obvious mismatches for 0 tokens), and batch scoring (up to 25 jobs per request).
- **Unified Engine:** The CLI, background daemon, and the Web UI share the exact same orchestration pipeline.
- **Cross-Platform:** Runs natively on **Windows** (via PowerShell `run.ps1`), **macOS** (launchd plists or bash), and **Linux**.

---

## 🚀 Quickstart

### 1. Requirements & Setup

JobTrace requires **Python 3.10+**.

```bash
# Clone the repository
git clone https://github.com/suvamneog/jobradar.git
cd jobradar

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Telegram & Preferences

Copy the configuration template:
```bash
cp config.example.yaml config.yaml
```

Set up your Telegram Bot:
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, name your bot (e.g. `MyJobTraceBot`), and copy your **Bot Token**.
3. Open a chat with your new bot and click **Start**.
4. Retrieve your Telegram **Chat ID** (via [@userinfobot](https://t.me/userinfobot) or visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`).
5. Add your token and chat ID to `config.yaml`:

```yaml
telegram:
  bot_token: "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
  chat_id: "987654321"
```

Verify your Telegram connection:
```bash
# Windows
.\run.ps1 test

# macOS / Linux
python3 -m jobtrace.main test
```
*You will immediately receive a test greeting message from JobTrace in Telegram!*

### 3. Add Your Resume

Drop your resume into the project directory (e.g., `resume.pdf` or `resume.txt`) and configure `resume_path` in `config.yaml`.

---

## 🛠️ CLI Commands

JobTrace comes with a comprehensive CLI:

```bash
# Fetch and score all configured sources
python -m jobtrace.main scan

# Send same-day alerts for watched shortlist companies to Telegram
python -m jobtrace.main alert
python -m jobtrace.main alert --dry-run

# Send weekly digest of top matches to Telegram
python -m jobtrace.main digest
python -m jobtrace.main digest --dry-run

# Run full scan followed by weekly digest
python -m jobtrace.main run

# Re-apply seniority and relevance gates to existing database (0 tokens)
python -m jobtrace.main recap

# Inspect recent openings directly in your terminal
python -m jobtrace.main list --days 7

# Launch the real-time Web Dashboard (http://localhost:8765)
python -m jobtrace.main web

# Run cross-platform background scheduler daemon
python -m jobtrace.main daemon
```

On Windows, use the included PowerShell script:
```powershell
.\run.ps1 scan
.\run.ps1 alert
.\run.ps1 web
```

---

## 🖥️ Live Web Dashboard

Launch the web UI to browse jobs, run live scans, and search job descriptions with SQLite FTS5:

```bash
python -m jobtrace.main web --port 8765
```

Navigate to `http://localhost:8765`:
- **Real-Time Scan Streaming:** Watch jobs get fetched, diffed, and scored via Server-Sent Events (SSE).
- **Full-Text Search (FTS5):** Search across titles, companies, locations, and descriptions.
- **Score Breakdown:** View radar breakdowns for skills, seniority, domain, location, and reach.

---

## ⏰ Automated Scheduling

### Option A: Built-in Background Daemon (Cross-Platform)
Run JobTrace as a persistent background process on any OS:
```bash
python -m jobtrace.main daemon
```
This checks daily alerts at 09:30 and dispatches weekly digests on Mondays at 09:00.

### Option B: macOS launchd
Install system agents for automatic runs:
```bash
sed "s|__DIR__|$(pwd)|g" com.jobtrace.daily.plist > ~/Library/LaunchAgents/com.jobtrace.daily.plist
sed "s|__DIR__|$(pwd)|g" com.jobtrace.weekly.plist > ~/Library/LaunchAgents/com.jobtrace.weekly.plist
launchctl load ~/Library/LaunchAgents/com.jobtrace.daily.plist
launchctl load ~/Library/LaunchAgents/com.jobtrace.weekly.plist
```

---

## 🧠 LLM Scoring Backends

JobTrace supports multiple scoring providers in `config.yaml`:
- **xkiro / OpenAI-compatible:** (`xkiro`, `openai`, `openrouter`)
- **Ollama:** Offline local inference
- **Cursor Cloud Agents:** Cloud agent execution
- **TypeSafe / JEV:** System One architecture
- **Local:** Built-in offline keyword, location, and seniority matcher (zero API keys required!)

---

## 🧪 Testing

Run the full automated test suite:
```bash
python -m unittest discover tests
```
Or run individual test modules:
```bash
python tests/test_store.py
python tests/test_telegram.py
python tests/test_sources.py
python tests/test_seniority.py
python tests/test_pipeline.py
```

---

## 📁 Project Structure

```
jobtrace/
├── jobtrace/                  # Core Python Package
│   ├── __init__.py
│   ├── main.py               # CLI dispatcher & subcommands
│   ├── pipeline.py           # Unified scan & score pipeline
│   ├── telegram.py           # Telegram Bot alert & digest dispatcher
│   ├── store.py              # SQLite store with FTS5 and presence tracking
│   ├── sources.py            # 7 ATS adapters & aggregators
│   ├── seniority.py          # Configurable seniority gate
│   ├── relevance.py          # Relevance scoring gate
│   ├── resume.py             # Resume parser & profile extractor
│   ├── budget.py             # Daily token economy & limits
│   ├── scheduler.py          # Cross-platform background runner
│   ├── batch.py              # Prompt batching & response salvage
│   ├── localmatch.py         # Offline matcher (0 tokens)
│   ├── llm.py                # LLM client abstractions
│   ├── cursor.py             # Cursor agent scoring
│   ├── jev.py                # TypeSafe JEV scoring
│   └── web/                  # FastAPI Web Dashboard & static assets
│       ├── server.py
│       └── static/
│           ├── index.html
│           ├── app.js
│           └── styles.css
├── tests/                    # Unit test suite
├── config.example.yaml       # Configuration template
├── requirements.txt          # Python dependencies
├── run.ps1                   # Windows runner
├── run.example.sh            # Linux / macOS runner
├── run-web.sh                # Web server launcher
└── com.jobtrace.*.plist      # macOS service descriptors
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
