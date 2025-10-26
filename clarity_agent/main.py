import typer
import asyncio
from rich.console import Console
from rich.panel import Panel
from typing_extensions import Annotated
from typing import List

# These imports are all correct
from .mcp_server.server import start_mcp_server
from .utils.logging import logger
from .agents.analyst import AnalystAgent
from .agents.sentinel import SentinelAgent
from .agents.copilot import CoPilotAgent

# --- Initialization (Correct) ---
app = typer.Typer()
console = Console()

# --- Commands ---

@app.command()
def version():
    """Shows the application version."""
    console.print("Clarity Agent v0.1.0")

@app.command()
def start_mcp():
    """Starts the MCP server for remediation tools."""
    console.print("[bold green]Starting Clarity Agent MCP Server...[/bold green]")
    try:
        # THE FIX IS HERE: We directly call the function now, as it is no longer async.
        # Uvicorn handles the event loop internally.
        start_mcp_server()
    except KeyboardInterrupt:
        # Uvicorn will print its own shutdown message, but this is good for catching an early exit.
        console.print("\n[bold yellow]MCP Server shut down by user.[/bold yellow]")

@app.command()
def analyze(
    log_files: Annotated[List[str], typer.Argument(help="A list of log file paths to analyze.")]
):
    """Runs the reactive incident analysis using the Analyst Agent."""
    
    async def run_async_analysis():
        with console.status("[bold blue]🚀 Initializing Clarity Agent...[/bold blue]", spinner="dots") as status:
            
            status.update("[bold blue]📊 Parsing and consolidating log files...[/bold blue]")
            agent = AnalystAgent()
            
            # Pass the status object to the agent for dynamic updates
            report_panel, remediation_panel = await agent.run_analysis(log_files, status)
            
            status.update("[bold green]✨ Finalizing analysis report...[/bold green]")
            
        console.print("\n")
        console.print("🎯 [bold green]Analysis Complete[/bold green] 🎯")
        console.print()
        
        # Display the professional panels
        if report_panel:
            console.print(report_panel)
            console.print()
        if remediation_panel:
            console.print(remediation_panel)
            console.print()
        
        # Offer Co-Pilot interactive session
        from rich.prompt import Confirm
        if Confirm.ask("[bold cyan]🤖 Would you like to start an interactive investigation with the Co-Pilot Agent?[/bold cyan]"):
            console.print()
            
            # Get analysis data for Co-Pilot
            copilot_data = agent.get_analysis_data_for_copilot()
            if copilot_data:
                copilot = CoPilotAgent()
                copilot.start_interactive_session(
                    incident_data={"log_files": log_files},
                    timeline_data=copilot_data["timeline_data"],
                    analysis_result=copilot_data["analysis_result"]
                )
            else:
                console.print("[red]No analysis data available for Co-Pilot session.[/red]")

    # Use asyncio.run() to execute our async top-level function
    asyncio.run(run_async_analysis())

@app.command()
def monitor(
    log_files: Annotated[List[str], typer.Argument(help="A list of log file paths to monitor for trends.")]
):
    """Starts proactive monitoring using the Sentinel Agent to detect trends before they become incidents."""
    
    async def run_async_monitoring():
        with console.status("[bold green]🛡️ Initializing Sentinel Agent for proactive monitoring...[/bold green]", spinner="dots") as status:
            
            status.update("[bold blue]🔧 Setting up monitoring infrastructure...[/bold blue]")
            sentinel = SentinelAgent()
            
            console.print("\n")
            console.print("🛡️ [bold green]Sentinel Agent Activated[/bold green] 🛡️")
            console.print("[dim]Press Ctrl+C to stop monitoring[/dim]")
            console.print()
            
            # Start monitoring (this will run until interrupted)
            await sentinel.start_monitoring(log_files, status)
            
        console.print("\n")
        console.print("🛑 [bold yellow]Proactive Monitoring Stopped[/bold yellow]")

    # Use asyncio.run() to execute our async monitoring function
    asyncio.run(run_async_monitoring())

# --- Application Entry Point (Correct) ---
if __name__ == "__main__":
    app()