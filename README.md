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

## ✨ Key Capabilities

* **🧠 AI-Driven RCA:** Utilizes **AWS Bedrock (Amazon Titan)** for high-confidence root cause analysis with supporting evidence.
* **✨ Three-Agent AI System:** A multi-agent architecture where specialized agents collaborate to solve complex problems:
    * **🛡️ Sentinel Agent (Proactive):** Continuously monitors log streams for negative trends (like rising error rates) and generates predictive alerts *before* an incident occurs.
    * **🔍 Analyst Agent (Reactive):** Activates during an incident to ingest logs, perform AI-powered RCA, and intelligently select a remediation command from the MCP server.
    * **🤖 Co-Pilot Agent (Interactive):** Activates after the analysis, allowing engineers to ask follow-up questions about the incident in plain English.
* **🛠️ Standards-Based Tooling:** Features an MCP-compatible server built with FastAPI that exposes remediation tools (e.g., `kubectl` commands) to the AI agents.
* **💎 Professional UX:** A beautiful and robust CLI built with **Rich** and **Typer**, featuring animated status spinners, color-coded syntax highlighting, and clean panel layouts.

---

## 🏗️ Architecture

```mermaid
graph TD
    subgraph User Interaction
        CLI[👨‍💻 Rich CLI Interface]
    end

    subgraph Clarity Agent Core
        Orchestrator["main.py (Orchestrator)"]
        Analyst["Analyst Agent"]
        Sentinel["Sentinel Agent"]
        CoPilot["Co-Pilot Agent"]
    end

    subgraph External Services & Tools
        Bedrock["AWS Bedrock (Titan Model)"]
        MCPServer["MCP Server (FastAPI)"]
    end

    CLI -- "Executes 'analyze' or 'monitor'" --> Orchestrator
    Orchestrator -- "Triggers" --> Analyst
    Orchestrator -- "Triggers" --> Sentinel
    Analyst -- "Sends prompt to" --> Bedrock
    Bedrock -- "Returns JSON analysis" --> Analyst
    Analyst -- "Intelligently chooses & calls tool" --> MCPServer
    MCPServer -- "Returns command" --> Analyst
    Analyst -- "Returns report, hands off to" --> CoPilot
    CoPilot -- "Takes user input" --> CLI
    CoPilot -- "Sends prompt to" --> Bedrock
    CoPilot -- "Returns answer to" --> CLI
🚀 Quick StartPrerequisitesPython 3.11+An active Python virtual environment (venv).AWS CLI configured with hackathon credentials (e.g., via aws configure sso).InstallationClone the repository:Bashgit clone [https://github.com/kp183/clarity-agent.git](https://github.com/kp183/clarity-agent.git)
cd clarity-agent
Activate your virtual environment:Bash# On Windows
.\venv\Scripts\Activate.ps1

# On macOS/Linux
source venv/bin/activate
Install all dependencies:Bashpip install ".[dev]"
AWS Bedrock SetupEnsure your provided hackathon AWS account has access to the Amazon Bedrock service in the us-east-1 region.Ensure you have enabled access for the Amazon Titan model provider on the "Model access" page of the Bedrock console.Log in to your AWS account via the CLI (e.g., aws sso login ...). The application will automatically use these credentials.📖 Complete Usage GuideThe agent runs in two separate terminals.1. Start the MCP Server (Terminal 1)This server must be running for the Analyst agent to suggest remediation commands.Bashpython -m clarity_agent.main start-mcp
2. Run Reactive Analysis (Terminal 2)This triggers the Analyst Agent and then the Co-Pilot Agent.Bash# Provide the paths to all incident log files
python -m clarity_agent.main analyze .\logs\app_errors.log .\logs\config_changes.csv .\logs\deployment_logs.json .\logs\db_performance.log
After the analysis, you will be prompted to start an interactive investigation with the Co-Pilot. Type Y to begin asking questions.3. Run Proactive Monitoring (Terminal 2)This triggers the Sentinel Agent to watch a log file for bad trends.Bash# Point the monitor at a live log file
python -m clarity_agent.main monitor .\logs\live_db_feed.log
The agent will scan the file every 30 seconds and print a report. Press CTRL+C to stop.📊 Example Output (Reactive Analysis)--- Analysis Complete ---
╭────────── AI Root Cause Analysis (from AWS Bedrock) ───────────╮
│ {                                                              │
│   "summary": "Database connection pool exhaustion.",            │
│   "root_cause_description": "The auth-service is experiencing...│
│   "affected_components": [                                     │
│     "auth-service",                                            │
│     "database"                                                 │
│   ],                                                           │
│   "confidence_score": 0.95                                     │
│ }                                                              │
╰────────────────────────────────────────────────────────────────╯
╭───────── AI Suggested Remediation (from MCP Server) ───────────╮
│ kubectl rollout restart deployment/auth-service -n default     │
╰────────────────────────────────────────────────────────────────╯
🛠️ Technical StackComponentTechnology / LibraryAI EngineAWS Bedrock (Amazon Titan)Tooling ProtocolMCP (via FastAPI)CLI FrameworkTyper & RichData ProcessingPandasAWS IntegrationBoto3LanguagePython 3.11+ConcurrencyAsyncio🔮 Future RoadmapWith the 3-agent core system complete, the future roadmap focuses on enterprise-grade hardening and integration:Security & Compliance: Implement comprehensive audit logging for all agent decisions and user actions. Add role-based access controls (RBAC).Performance Optimization: Scale log processing to handle massive (1GB+) log files efficiently.Integration Ecosystem: Build connectors for Slack, PagerDuty, and Jira to send alerts and reports directly to existing workflows.Persistence: Integrate the database models to save all incident analyses and create a historical knowledge base.<p align="center"><strong>Built with ❤️ for the IT Operations community.</strong></p>
