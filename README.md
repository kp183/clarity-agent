# 🤖 Clarity Agent

**AI-Powered IT Operations Automation for Incident Analysis and Remediation**

<p align="center">
  <img src="https://img.shields.io/badge/AWS-Bedrock-orange?style=for-the-badge" alt="AWS Bedrock"/>
  <img src="https://img.shields.io/badge/AI_Model-Amazon_Titan-F8991D?style=for-the-badge" alt="Amazon Titan"/>
  <img src="https://img.shields.io/badge/SDK-Strands-informational?style=for-the-badge" alt="Strands SDK"/>
  <img src="https://img.shields.io/badge/Protocol-FastMCP-lightgrey?style=for-the-badge" alt="FastMCP"/>
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/CLI-Rich_&_Typer-purple?style=for-the-badge" alt="Rich & Typer CLI"/>
</p>

Clarity Agent automates Root Cause Analysis (RCA) by analyzing logs, correlating events, and suggesting safe, context-aware remediation actions. It combines a human-friendly CLI with AWS Bedrock and an MCP-compatible tool server to shorten incident resolution from hours to minutes.

---

## ✨ **Key Capabilities: A Three-Agent AI System**

### 🔍 **1. Analyst Agent (Reactive Incident Analysis)**
-   **AI-Powered RCA**: Connects to **AWS Bedrock (Amazon Titan)** for high-confidence root cause analysis.
-   **Multi-Format Parsing**: Ingests and consolidates JSON, CSV, and plain text logs into a single timeline.
-   **Intelligent Remediation**: Intelligently selects the correct `kubectl` command (e.g., `restart` vs. `rollback`) by analyzing the AI's findings and calling a standards-compliant **MCP server**.

### 🛡️ **2. Sentinel Agent (Proactive Monitoring)**
-   **Continuous Monitoring**: Runs as a background service, automatically scanning log files for negative trends.
-   **Predictive Alerts**: Uses AI to generate high-severity warnings (e.g., "high error rate detected") *before* an incident occurs.
-   **Rich Dashboard**: Displays a professional monitoring table in the console, showing scan status in real-time.

### 🤖 **3. Co-Pilot Agent (Interactive Investigation)**
MIT — see the LICENSE file for details.
