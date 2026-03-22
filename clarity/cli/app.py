"""
Clarity CLI — Main command-line interface.

Provides commands: analyze, monitor, ticket, start-mcp, version
"""

import sys
import os
import typer
import asyncio
import json
import re

# Fix Windows terminal encoding for emoji/unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from typing_extensions import Annotated
from typing import List

from ..agents.analyst import AnalystAgent
from ..agents.sentinel import SentinelAgent
from ..agents.copilot import CoPilotAgent
from ..config import settings

app = typer.Typer(
    name="clarity",
    help="Clarity: AI DevOps Copilot -- Intelligent incident management",
    add_completion=False,
)
console = Console(force_terminal=True)


# ─── Commands ────────────────────────────────────

@app.command()
def version():
    """Show the Clarity version."""
    from .. import __version__
    console.print(f"[bold cyan]Clarity[/bold cyan] v{__version__}")


@app.command()
def analyze(
    log_files: Annotated[List[str], typer.Argument(help="Log file paths to analyze.")]
):
    """Run reactive incident analysis using the Analyst Agent."""

    async def _run():
        with console.status("[bold blue]🚀 Initializing Clarity...[/bold blue]", spinner="dots") as status:
            agent = AnalystAgent()
            report_panel, remediation_panel = await agent.run_analysis(log_files, status)

        console.print("\n")
        console.print("🎯 [bold green]Analysis Complete[/bold green] 🎯")
        console.print()

        if report_panel:
            console.print(report_panel)
            console.print()
        if remediation_panel:
            console.print(remediation_panel)
            console.print()

        # Explicit confirmation before any remediation execution path
        from rich.prompt import Confirm
        Confirm.ask("Execute this remediation command?")

        # Audit log — record that analysis + remediation display completed
        from ..core.audit import write_audit_log
        copilot_data = agent.get_analysis_data_for_copilot()
        remediation_cmd = copilot_data.get("remediation_command", "") if copilot_data else ""
        write_audit_log(
            action="analyze",
            outcome="remediation_displayed",
            user_context={"log_files": log_files, "remediation_command": remediation_cmd},
        )

        # Offer Co-Pilot session
        if Confirm.ask("[bold cyan]🤖 Start interactive investigation with Co-Pilot?[/bold cyan]"):
            console.print()
            copilot_data = agent.get_analysis_data_for_copilot()
            if copilot_data:
                copilot = CoPilotAgent()
                copilot.start_interactive_session(
                    incident_data={"log_files": log_files},
                    timeline_data=copilot_data["timeline_data"],
                    analysis_result=copilot_data["analysis_result"],
                )
            else:
                console.print("[red]No analysis data available for Co-Pilot.[/red]")

    asyncio.run(_run())


@app.command()
def ticket(
    log_files: Annotated[List[str], typer.Argument(help="Log file paths to analyze for ticket.")]
):
    """Generate a professional incident report for ticketing systems."""

    async def _run():
        with console.status("[bold blue]🚀 Analyzing for ticket generation...[/bold blue]", spinner="dots") as status:
            agent = AnalystAgent()
            report_panel, remediation_panel = await agent.run_analysis(log_files, status)

        console.print("\n")
        console.print("🎯 [bold green]Analysis Complete[/bold green] 🎯")
        console.print()

        if report_panel:
            console.print(report_panel)
            console.print()
        if remediation_panel:
            console.print(remediation_panel)
            console.print()

        # Generate ticket
        copilot_data = agent.get_analysis_data_for_copilot()
        analysis_str = copilot_data.get("analysis_result", "") if copilot_data else ""
        remediation_cmd = copilot_data.get("remediation_command", "") if copilot_data else ""

        ticket_md = _format_ticket(analysis_str, remediation_cmd)

        console.print(Panel(
            Syntax(ticket_md, "markdown", theme="monokai", word_wrap=True),
            title="[bold blue]📋 Formatted Ticket Update (Copy Below)[/bold blue]",
            subtitle="[dim]Ready for Jira, ServiceNow, or any ticketing system[/dim]",
            border_style="blue",
            expand=True,
            padding=(1, 2),
        ))
        console.print()
        console.print("[dim]💡 Copy the content above and paste into your incident ticket[/dim]")

    asyncio.run(_run())


@app.command()
def monitor(
    log_files: Annotated[List[str], typer.Argument(help="Log file paths to monitor.")]
):
    """Start proactive monitoring with the Sentinel Agent."""

    async def _run():
        with console.status("[bold green]🛡️ Initializing Sentinel...[/bold green]", spinner="dots") as status:
            sentinel = SentinelAgent()
            console.print("\n🛡️ [bold green]Sentinel Activated[/bold green] 🛡️")
            console.print("[dim]Press Ctrl+C to stop[/dim]\n")
            await sentinel.start_monitoring(log_files, status)

        console.print("\n🛑 [bold yellow]Monitoring Stopped[/bold yellow]")

    asyncio.run(_run())


@app.command(name="start-mcp")
def start_mcp():
    """Start the MCP remediation tool server."""
    import uvicorn
    from ..mcp.server import mcp_app

    console.print("[bold green]🚀 Starting Clarity MCP Server...[/bold green]")
    try:
        uvicorn.run(
            mcp_app,
            host=settings.mcp_server_host,
            port=settings.mcp_server_port,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[bold yellow]MCP Server shut down.[/bold yellow]")


@app.command(name="start-api")
def start_api(port: int = 8000):
    """Start the Clarity REST API backend for the web dashboard."""
    import uvicorn
    from ..api.server import app as api_app

    console.print(f"[bold green]🚀 Starting Clarity REST API on port {port}...[/bold green]")
    try:
        uvicorn.run(
            api_app,
            host="0.0.0.0",
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[bold yellow]REST API shut down.[/bold yellow]")


@app.command(name="export-report")
def export_report(
    log_files: Annotated[List[str], typer.Argument(help="Log file paths to analyze.")],
    output: str = typer.Option("report.md", help="Output file path."),
    fmt: str = typer.Option("markdown", help="Format: markdown or json."),
):
    """Analyze logs and export a professional incident report."""

    async def _run():
        with console.status("[bold blue]🚀 Analyzing for report...[/bold blue]", spinner="dots") as status:
            agent = AnalystAgent()
            await agent.run_analysis(log_files, status)

        copilot_data = agent.get_analysis_data_for_copilot()
        analysis_str = copilot_data.get("analysis_result", "") if copilot_data else ""
        remediation_cmd = copilot_data.get("remediation_command", "") if copilot_data else ""
        timeline = copilot_data.get("timeline_data", []) if copilot_data else []

        from ..integrations.report_exporter import ReportExporter
        exporter = ReportExporter()

        if fmt.lower() == "json":
            content = exporter.to_json(analysis_str, timeline, remediation_cmd)
            if not output.endswith(".json"):
                output_path = output.rsplit(".", 1)[0] + ".json"
            else:
                output_path = output
        else:
            content = exporter.to_markdown(analysis_str, timeline, remediation_cmd)
            output_path = output

        exporter.save(content, output_path)
        console.print(f"\n[bold green]✅ Report exported to:[/bold green] {output_path}")

    asyncio.run(_run())


@app.command()
def notify(
    log_files: Annotated[List[str], typer.Argument(help="Log file paths to analyze.")],
    slack: bool = typer.Option(False, help="Send report to Slack."),
    jira: bool = typer.Option(False, help="Create a Jira ticket."),
):
    """Analyze logs and send notifications to Slack/Jira."""

    async def _run():
        with console.status("[bold blue]🚀 Analyzing...[/bold blue]", spinner="dots") as status:
            agent = AnalystAgent()
            await agent.run_analysis(log_files, status)

        copilot_data = agent.get_analysis_data_for_copilot()
        analysis_str = copilot_data.get("analysis_result", "") if copilot_data else ""
        remediation_cmd = copilot_data.get("remediation_command", "") if copilot_data else ""

        from ..integrations.report_exporter import ReportExporter
        exporter = ReportExporter()
        report_md = exporter.to_markdown(analysis_str,
                                          copilot_data.get("timeline_data", []) if copilot_data else [],
                                          remediation_cmd)

        if slack:
            from ..integrations.slack import SlackNotifier
            webhook = os.environ.get("SLACK_WEBHOOK_URL")
            notifier = SlackNotifier(webhook_url=webhook)
            result = notifier.send_incident_report(report_md)
            if result["ok"]:
                console.print("[bold green]✅ Slack notification sent[/bold green]")
            else:
                console.print("[red]❌ Slack notification failed[/red]")

        if jira:
            from ..integrations.jira import JiraClient
            client = JiraClient(
                base_url=os.environ.get("JIRA_BASE_URL"),
                project_key=os.environ.get("JIRA_PROJECT_KEY", "INC"),
                email=os.environ.get("JIRA_EMAIL"),
                api_token=os.environ.get("JIRA_API_TOKEN"),
            )
            parsed = exporter._parse_analysis(analysis_str)
            result = client.create_incident_ticket(
                summary=parsed.get("summary", "AI-detected incident"),
                description=report_md,
                severity=_severity_from_confidence(parsed.get("confidence_score", 0.5)),
                affected_services=parsed.get("affected_components", []),
            )
            console.print(f"[bold green]✅ Jira ticket created:[/bold green] {result.get('key', 'N/A')}")

        if not slack and not jira:
            console.print("[yellow]⚠️ No notification target specified. Use --slack and/or --jira[/yellow]")

    asyncio.run(_run())


def _severity_from_confidence(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


# ─── Helpers ─────────────────────────────────────

def _format_ticket(analysis_str: str, remediation_cmd: str) -> str:
    """Format analysis into a professional Markdown ticket update."""
    try:
        json_match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            data = {
                "summary": "Analysis data unavailable",
                "root_cause_description": "Could not parse analysis",
                "affected_components": ["unknown"],
                "confidence_score": 0.0,
            }
    except (json.JSONDecodeError, AttributeError):
        data = {
            "summary": "Analysis parsing error",
            "root_cause_description": "Could not parse analysis from AI response",
            "affected_components": ["unknown"],
            "confidence_score": 0.0,
        }

    import datetime
    components = "\n".join(f"• {c}" for c in data.get("affected_components", ["unknown"]))

    return f"""### 🤖 AI-Powered Incident Report

**Summary:** {data.get('summary', 'N/A')}

**Root Cause Analysis:**
{data.get('root_cause_description', 'N/A')}

**Affected Components:**
{components}

**AI Confidence Score:** {data.get('confidence_score', 0.0):.1%}

**Recommended Remediation:**
```bash
{remediation_cmd}
```

**Analysis Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

---
*Generated by Clarity AI (Amazon Titan via AWS Bedrock)*"""
