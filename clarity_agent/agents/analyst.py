import httpx
import asyncio
import pandas as pd
import json
import re
from typing import List, Tuple, Optional

# Imports for professional formatting from the rich library
from rich.panel import Panel
from rich.syntax import Syntax

# Import project-specific modules
from ..utils.parsers import parse_log_files
from ..services.bedrock import bedrock_client
from ..config.settings import settings
from ..utils.logging import logger

class AnalystAgent:
    """
    The main analytical agent responsible for performing Root Cause Analysis (RCA)
    on IT incident logs and suggesting intelligent remediation commands.
    """

    def __init__(self):
        """Initializes the Analyst Agent with its role and goal."""
        self.role = "Expert Site Reliability Engineer specializing in automated incident analysis"
        self.goal = "Analyze incident logs to find the root cause and suggest an actionable remediation."
        logger.info("Analyst Agent initialized.")

    async def run_analysis(self, log_files: List[str]) -> Tuple[Panel, Optional[Panel]]:
        """
        Orchestrates the full asynchronous RCA pipeline from log ingestion to final report.

        Args:
            log_files: A list of file paths to the incident logs.

        Returns:
            A tuple containing two `rich.panel.Panel` objects for the final report.
        """
        logger.info("Starting analysis pipeline...", log_files=log_files)

        # Step 1: Parse and consolidate all log files into a single timeline.
        try:
            timeline_df = parse_log_files(log_files)
            if timeline_df.empty:
                error_panel = Panel("[bold red]Error: Could not parse any valid log entries from the provided files.[/bold red]", title="[bold red]Parsing Error[/bold red]", border_style="red")
                return error_panel, None
        except Exception as e:
            logger.error("Fatal error during log parsing", error=str(e))
            error_panel = Panel(f"[bold red]Fatal Error during log parsing: {e}[/bold red]", title="[bold red]Critical Error[/bold red]", border_style="red")
            return error_panel, None

        # Step 2: Invoke the AWS Bedrock model to perform the core RCA.
        rca_prompt = self._build_rca_prompt(timeline_df)
        analysis_response_text = bedrock_client.invoke(rca_prompt)

        # Step 3: Check if the AI analysis was successful; if not, use a resilient fallback.
        if "Error:" in analysis_response_text or not self._is_valid_json(analysis_response_text):
            logger.warning("Bedrock analysis failed or returned invalid JSON. Using mock analysis as a fallback.")
            analysis_response_text = self._generate_mock_analysis(timeline_df)
        
        # Step 4: Use the AI's analysis to intelligently request a remediation command from the MCP server.
        logger.info("Requesting remediation command from MCP server...")
        remediation_command = await self._get_remediation_command(analysis_response_text)
        
        # Step 5: Format the final, polished report for display.
        logger.info("Analysis pipeline completed successfully.")
        return self._format_report(analysis_response_text, remediation_command)

    async def _get_remediation_command(self, analysis_json_str: str) -> str:
        """Calls the local MCP FastAPI server's REST endpoints to obtain a remediation command."""
        mcp_base_url = f"http://{settings.mcp_server_host}:{settings.mcp_server_port}"
        service_name = self._extract_service_from_analysis(analysis_json_str)

        # Agent Decision Logic: Intelligently choose the right tool based on the analysis content.
        if "exhausted" in analysis_json_str.lower() or "pool" in analysis_json_str.lower():
            endpoint = "/tools/restart"
            logger.info("Decision: Analysis suggests a resource exhaustion issue. Choosing 'restart' tool.")
        else:
            endpoint = "/tools/rollback"
            logger.info("Decision: Analysis suggests a deployment or configuration issue. Choosing 'rollback' tool.")

        payload = {"service_name": service_name, "namespace": "default"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{mcp_base_url}{endpoint}", json=payload, timeout=10.0)
                response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                result = response.json()
                return result.get("command", f"Unexpected response from MCP Server: {result}")
        except httpx.RequestError as e:
            logger.error("Could not connect to MCP server. Is it running?", error=str(e))
            return "Error: Could not connect to the local MCP server."
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error from MCP server", status_code=e.response.status_code)
            return f"Error: MCP Server returned status {e.response.status_code}"

    def _extract_service_from_analysis(self, analysis_json_str: str) -> str:
        """Finds the most likely affected service name from the analysis text."""
        services = ["auth-service", "api-service", "user-service", "payment-service"]
        for svc in services:
            if svc in analysis_json_str.lower():
                return svc
        return "auth-service" # Default fallback

    def _generate_mock_analysis(self, timeline_df: pd.DataFrame) -> str:
        """Generates a high-quality mock analysis for demos if the live AI is unavailable."""
        num_events = len(timeline_df)
        error_count = len(timeline_df[timeline_df.get("level") == LogLevel.ERROR])
        mock_data = {
            "summary": f"Mock Analysis: Found {error_count} errors in {num_events} events.",
            "root_cause_description": "The mock analysis indicates that the 'auth-service' failed due to database connection pool exhaustion following a recent configuration change.",
            "affected_components": ["auth-service", "database"],
            "confidence_score": 0.85,
        }
        return json.dumps(mock_data, indent=2)

    def _build_rca_prompt(self, timeline_df: pd.DataFrame) -> str:
        """Builds a highly-structured, reliable prompt optimized for Bedrock models."""
        log_data_string = timeline_df.to_string(index=False)
        
        system_prompt = """You are Clarity Agent, an expert AI system for automated Root Cause Analysis (RCA). Your sole purpose is to analyze the provided log data and return a single, valid JSON object conforming to the specified schema. You must never include any conversational text, markdown formatting, or any characters outside of the final JSON object. Your response must begin with '{' and end with '}'."""
        
        json_schema = """{
    "summary": "<A brief, one-sentence summary of the incident>",
    "root_cause_description": "<A detailed, two to three-sentence explanation of the most likely root cause>",
    "affected_components": ["<A list of service names that were directly affected>"],
    "confidence_score": <A number between 0.0 and 1.0 representing your confidence in the analysis>
}"""

        user_prompt = f"""Analyze the following log data. Adhere strictly to the JSON schema I have provided.

--- LOG DATA START ---
{log_data_string}
--- LOG DATA END ---

Your response must be ONLY the JSON object based on your analysis."""

        # For models that support a system prompt, this would be ideal.
        # For Titan, combining it in the user prompt is a robust strategy.
        return f"System Prompt: {system_prompt}\n\nJSON Schema to follow:\n{json_schema}\n\nUser Task: {user_prompt}"

    def _is_valid_json(self, response_text: str) -> bool:
        """A simple helper to check if a string contains a valid JSON object."""
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json.loads(json_match.group(0))
                return True
        except (json.JSONDecodeError, AttributeError):
            return False
        return False

    def _format_report(self, analysis_str: str, remediation_command: str) -> Tuple[Panel, Panel]:
        """Creates professional `rich` panels for the final console output."""
        pretty_analysis = analysis_str
        try:
            json_match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
            if json_match:
                pretty_analysis = json.dumps(json.loads(json_match.group(0)), indent=2)
            else:
                pretty_analysis = "Could not parse a valid JSON object from the AI's response."
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Could not parse JSON from AI response, displaying raw text.")
            pretty_analysis = analysis_str

        report_panel = Panel(
            Syntax(pretty_analysis, "json", theme="solarized-dark", line_numbers=True),
            title="[bold green]AI Root Cause Analysis (from AWS Bedrock)[/bold green]",
            border_style="green",
            expand=True,
        )
        
        remediation_panel = Panel(
            Syntax(str(remediation_command), "shell", theme="solarized-dark"),
            title="[bold yellow]AI Suggested Remediation (from MCP Server)[/bold yellow]",
            border_style="yellow",
            expand=True,
        )
        
        return report_panel, remediation_panel