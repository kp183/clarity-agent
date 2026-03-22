# Clarity Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Clarity Platform                          │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│  │ Analyst  │  │ Sentinel │  │ Co-Pilot │   ← AI Agents         │
│  │  Agent   │  │  Agent   │  │  Agent   │                       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                       │
│       │              │             │                             │
│       └──────────────┼─────────────┘                             │
│                      │                                           │
│  ┌───────────────────┴───────────────────┐                       │
│  │          Core Services Layer          │                       │
│  │  ┌─────────┐ ┌────────┐ ┌─────────┐  │                       │
│  │  │LLM Clnt │ │ Parser │ │ Models  │  │                       │
│  │  └─────────┘ └────────┘ └─────────┘  │                       │
│  └───────────────────┬───────────────────┘                       │
│                      │                                           │
│  ┌─────────────┐  ┌──┴───────┐  ┌──────────┐                    │
│  │  Typer CLI  │  │ FastAPI  │  │ MCP Srvr │   ← Interfaces     │
│  └─────────────┘  │ REST API │  │ (Tools)  │                    │
│                   └──────────┘  └──────────┘                    │
│                      │                                           │
│               ┌──────┴──────┐                                    │
│               │  Next.js    │   ← Web Dashboard                  │
│               │  Dashboard  │                                    │
│               └─────────────┘                                    │
└──────────────────────────────────────────────────────────────────┘
```

## Agent Responsibilities

### Analyst Agent
- Parses multi-format log files (JSON, JSONL, CSV, text)
- Builds incident timelines
- Invokes Amazon Titan for root cause analysis (RCA)
- Requests remediation commands from MCP server
- Generates professional incident reports

### Sentinel Agent
- Continuous proactive monitoring of log sources
- Rule-based threshold detection (error rate, latency)
- AI-powered predictive analysis via Amazon Titan
- Configurable alert thresholds and severity levels
- Real-time Rich terminal dashboard

### Co-Pilot Agent
- Interactive Q&A chat interface for incident investigation
- Contextual answers using incident data + LLM
- Rule-based fallback for offline operation
- Conversation history and session export
- Professional report generation (Markdown / JSON)

## Data Flow

1. **Log Ingestion**: Raw logs → `parsers/log_parser.py` → Normalized `DataFrame`
2. **Analysis**: `DataFrame` → Analyst Agent → Amazon Titan RCA → `AnalysisResult`
3. **Monitoring**: `DataFrame` → Sentinel Agent → Trend detection + AI prediction → `ProactiveAlert`
4. **Investigation**: Analysis context → Co-Pilot Agent → Interactive Q&A
5. **Remediation**: RCA output → MCP Server → Remediation commands
6. **Dashboard**: REST API → Next.js frontend → Real-time display

## Technology Stack

| Layer       | Technology                 |
|-------------|----------------------------|
| AI/LLM      | AWS Bedrock (Amazon Titan) |
| Backend     | Python 3.11+, FastAPI      |
| CLI         | Typer + Rich               |
| Frontend    | Next.js + TypeScript       |
| Styling     | Tailwind CSS               |
| Testing     | pytest + pytest-asyncio    |
| Container   | Docker + docker-compose    |
| Database    | SQLite (dev) / PostgreSQL  |
