# ⚡ Clarity — AI DevOps Copilot

> Cut incident resolution time by 95%. From raw logs to root cause in 5 seconds.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green?style=flat-square)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?style=flat-square)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

Clarity is a free, open-source AI tool that analyzes production logs, identifies root causes, and suggests remediation — all in seconds. Built for DevOps engineers who live in the terminal.

---

## Quick Start

```bash
# Install
pip install -e .

# Copy env and add your Groq API key (free at console.groq.com)
cp .env.example .env

# Analyze logs
clarity analyze logs/app_errors.log

# Monitor continuously
clarity monitor logs/app_errors.log

# Generate incident ticket
clarity ticket logs/app_errors.log
```

---

## What It Does

**3 AI agents, one command:**

- `AnalystAgent` — parses your logs, builds a timeline, runs LLM-powered root cause analysis, returns a confidence-scored JSON result + kubectl remediation command
- `SentinelAgent` — continuously monitors log files, detects error rate spikes and subtle patterns (memory leaks, cascading failures) before they become outages
- `CoPilotAgent` — interactive Q&A after analysis. Ask "what happened right before the crash?" and get answers with specific timestamps

**Supports any log format:** JSON, JSONL, CSV, plain text, syslog — multiple files at once, consolidated into a single timeline.

**PII auto-redacted** before any data is processed (emails, phone numbers, API keys, Bearer tokens).

---

## CLI Commands

```bash
clarity analyze <log_files>      # Root cause analysis
clarity monitor <log_files>      # Proactive monitoring (Ctrl+C to stop)
clarity ticket <log_files>       # Generate markdown incident report
clarity notify <log_files> --slack --jira  # Send to Slack / create Jira ticket
clarity export-report <log_files> --output report.md  # Export full report
clarity start-api                # Start REST API backend (port 8000)
clarity start-mcp                # Start MCP remediation server (port 8001)
clarity version                  # Show version
```

---

## Web App

A Next.js frontend is included for browser-based log analysis.

```bash
cd web
npm install
npm run dev
# Open http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` to point at your running API backend.

---

## Configuration

```bash
cp .env.example .env
```

Key settings:

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | `groq` or `bedrock` |
| `GROQ_API_KEY` | Get free at [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL_ID` | Default: `llama-3.3-70b-versatile` |
| `AWS_PROFILE_NAME` | For Bedrock (optional) |
| `SLACK_WEBHOOK_URL` | For Slack notifications (optional) |
| `JIRA_BASE_URL` | For Jira ticket creation (optional) |

---

## Docker

```bash
# Run everything (API + MCP + Web)
docker-compose up -d

# API at :8000, MCP at :8001, Web at :3000
```

---

## Architecture

```
clarity/
├── agents/
│   ├── analyst.py      # Reactive RCA — parse → timeline → LLM → remediation
│   ├── sentinel.py     # Proactive monitoring — continuous scan + AI prediction
│   └── copilot.py      # Interactive Q&A with full incident context
├── api/
│   └── server.py       # FastAPI REST API (demo, analyze, chat, ticket endpoints)
├── cli/
│   └── app.py          # Typer CLI (analyze, monitor, ticket, notify, export)
├── core/
│   ├── llm_client.py   # Multi-provider LLM (Groq + AWS Bedrock)
│   └── models.py       # Pydantic data models
├── integrations/
│   ├── slack.py        # Slack notifications
│   ├── jira.py         # Jira ticket creation
│   └── report_exporter.py  # Markdown/JSON report export
├── mcp/
│   └── server.py       # MCP tool server (kubectl rollback/restart/scale)
└── parsers/
    └── log_parser.py   # Multi-format parser with PII redaction

web/                    # Next.js 14 frontend
demo_data/              # 3 realistic incident scenarios for demo
tests/                  # 210 tests (pytest + Hypothesis)
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

---

## LLM Providers

| Provider | Model | Setup |
|---|---|---|
| Groq (recommended) | `llama-3.3-70b-versatile` | Free API key at console.groq.com |
| AWS Bedrock | Amazon Titan / Claude / Nova | AWS account with Bedrock access |

---

## License

MIT — free to use, modify, and distribute.

---

## Contact

- GitHub: [github.com/kp183/clarity-agent](https://github.com/kp183/clarity-agent)
- Email: team@clarity.ai
