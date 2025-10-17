# 🤖 Clarity Agent

**AI-Powered IT Operations Automation for Incident Analysis and Remediation**

<p align="center">
  <img src="https://img.shields.io/badge/AWS-Bedrock-orange?style=for-the-badge" alt="AWS Bedrock"/>
  <img src="https://img.shields.io/badge/AI_Model-Amazon_Titan-F8991D?style=for-the-badge" alt="Amazon Titan"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/CLI-Rich_&_Typer-purple?style=for-the-badge" alt="Rich & Typer CLI"/>
  <img src="https://img.shields.io/badge/Protocol-MCP-lightgrey?style=for-the-badge" alt="MCP Protocol"/>
</p>

Clarity Agent automates Root Cause Analysis (RCA) by analyzing logs, correlating events, and suggesting safe, context-aware remediation actions. It combines a human-friendly CLI with AWS Bedrock and an MCP-compatible tool server to shorten incident resolution from hours to minutes.

---

### ## Key Capabilities

-   **🧠 AI-Driven RCA:** Utilizes **AWS Bedrock (Amazon Titan)** for high-confidence root cause analysis with supporting evidence.
-   **🛠️ Intelligent Remediation:** Makes context-aware decisions to select the appropriate remediation tool (e.g., `restart` vs. `rollback`) from a standards-compliant **MCP server**.
-   **🔍 Multi-Format Log Ingestion:** Natively parses and consolidates JSON, CSV, and plain text logs into a single chronological timeline.
-   **🛡️ Resilient by Design:** Includes a robust mock analysis fallback to ensure a smooth demo and functional use even when the external AI service fails.
-   **💎 Professional CLI Experience:** A beautiful and intuitive command-line interface powered by **Typer** and **Rich**, featuring syntax highlighting, spinners, and clean, readable panels.

---

### ## Architecture

```mermaid
graph TD
    subgraph User Interaction
        CLI[👨‍💻 Rich CLI Interface]
    end

    subgraph Clarity Agent Core
        Orchestrator["main.py (Orchestrator)"]
        Analyst["Analyst Agent"]
    end

    subgraph External Services & Tools
        Bedrock["AWS Bedrock (Titan Model)"]
        MCPServer["MCP Server (FastAPI)"]
    end

    CLI -- "Executes 'analyze' command" --> Orchestrator
    Orchestrator -- "Triggers" --> Analyst
    Analyst -- "Sends prompt to" --> Bedrock
    Bedrock -- "Returns JSON analysis" --> Analyst
    Analyst -- "Intelligently chooses & calls tool" --> MCPServer
    MCPServer -- "Returns command" --> Analyst
    Analyst -- "Returns final report to" --> Orchestrator
    Orchestrator -- "Prints beautiful report to" --> CLI
```

---

## Quick start

### Prerequisites

- Python 3.11+
- AWS CLI configured for Bedrock (region: us-east-1)
- Virtualenv or equivalent

### Install

```bash
git clone https://github.com/kp183/clarity-agent.git
cd clarity-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

### AWS Bedrock setup

1. Ensure your AWS account has permission to call Amazon Bedrock in `us-east-1`.
2. Configure credentials (SSO or programmatic) via `aws configure` or `aws configure sso`. The application will use the default AWS credential chain.

---

## Usage

Start the MCP server (background tool server used for remediation requests):

```bash
python -m clarity_agent.main start-mcp
```

Analyze one or more log files:

```bash
# Single file
python -m clarity_agent.main analyze ./logs/app_errors.log

# Multiple files
python -m clarity_agent.main analyze \
  ./logs/app_errors.log \
  ./logs/config_changes.csv \
  ./logs/deployment_logs.json \
  ./logs/db_performance.log
```

Check version / status:

```bash
python -m clarity_agent.main version
```

---

## Example output (trimmed)

```
--- Analysis Complete ---
╭── AI Root Cause Analysis ─────────────────────╮
│ {                                             │
│   "summary": "Database connection timeout",   │
│   "root_cause_description": "DB connection    │
│     pool exhausted due to slow queries",      │
│   "affected_components": ["auth-service"],    │
│   "confidence_score": 0.92                     │
│ }                                             │
╰────────────────────────────────────────────────╯

╭── AI Suggested Remediation (from MCP Server) ──╮
│ kubectl rollout undo deployment/auth-service    │
╰──────────────────────────────────────────────────╯
```

---

## Design principles

- Deterministic pipelines for parsing and correlation — reduce noise before AI is consulted.
- Explainability — every AI conclusion is accompanied by supporting log entries and a confidence score.
- Safety-first remediation — suggestions are presented for operator review; destructive actions are never automatic.
- Standardized integration — MCP protocol for tool invocation and observability.

---

## Technical stack

- AI: AWS Bedrock (LLM)
- Protocol: Model Context Protocol (MCP)
- CLI: Typer + Rich
- Parsing: pandas + custom parsers
- API: FastAPI (MCP server)
- Language: Python 3.11+
- Concurrency: asyncio

---

## Repository layout

```
clarity-agent/
├── clarity_agent/
│   ├── agents/          # AI agents (Analyst)
│   ├── models/          # Data models and schemas
│   ├── services/        # AWS Bedrock integration
│   ├── mcp_server/      # MCP-compatible server
│   ├── utils/           # Log parsers and utilities
│   ├── config/          # Configuration management
│   └── main.py          # CLI entry point
├── logs/                # Sample log files
├── tests/               # Test suite
└── README.md
```

---

## Roadmap

- Phase 2: Sentinel — continuous monitoring and predictive alerts
- Phase 3: Interactive Co-pilot — natural-language Q&A over incidents and histories
- Phase 4: Enterprise — RBAC, encryption, audit trails, and high-throughput processing

---

## Contributing

We welcome contributions. Please open issues or PRs and follow the project's contributing guidelines (code style, tests, PR process). For significant changes, open an issue first to discuss scope and design.

---

## License

MIT — see the LICENSE file.

---

## Acknowledgments

Thanks to AWS Bedrock, Model Context Protocol, Rich, and FastAPI for tools and inspiration.

---
Built with care for modern IT Operations — precise analysis, transparent reasoning, and operator-first remediation.
```

