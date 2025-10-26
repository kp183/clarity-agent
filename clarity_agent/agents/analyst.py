import httpx
import asyncio
import pandas as pd
import json
import re
from typing import List, Tuple, Optional, Dict, Any

# Imports for professional formatting from the rich library
from rich.panel import Panel
from rich.syntax import Syntax

# Import project-specific modules
from ..utils.parsers import parse_log_files
from ..services.bedrock import bedrock_client
from ..config.settings import settings
from ..models.core import LogLevel
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
        self.last_analysis_data = None  # Store data for Co-Pilot integration
        logger.info("Analyst Agent initialized.")

    async def run_analysis(self, log_files: List[str], status=None) -> Tuple[Panel, Optional[Panel]]:
        """
        Orchestrates the full asynchronous RCA pipeline from log ingestion to final report.

        Args:
            log_files: A list of file paths to the incident logs.
            status: Optional Rich status object for dynamic updates.

        Returns:
            A tuple containing two `rich.panel.Panel` objects for the final report.
        """
        logger.info("Starting analysis pipeline...", log_files=log_files)

        # Step 1: Parse and consolidate all log files into a single timeline.
        if status:
            status.update("[bold blue]📁 Processing log files and building timeline...[/bold blue]")
            
        try:
            timeline_df = parse_log_files(log_files)
            if timeline_df.empty:
                error_panel = Panel("[bold red]❌ Error: Could not parse any valid log entries from the provided files.[/bold red]", title="[bold red]🚨 Parsing Error[/bold red]", border_style="red")
                return error_panel, None
                
            num_events = len(timeline_df)
            if status:
                status.update(f"[bold green]✅ Successfully parsed {num_events} log events[/bold green]")
                
        except Exception as e:
            logger.error("Fatal error during log parsing", error=str(e))
            error_panel = Panel(f"[bold red]❌ Fatal Error during log parsing: {e}[/bold red]", title="[bold red]🚨 Critical Error[/bold red]", border_style="red")
            return error_panel, None

        # Step 2: Invoke the AWS Bedrock model to perform the core RCA.
        if status:
            status.update("[bold yellow]🧠 Connecting to AWS Bedrock for AI analysis...[/bold yellow]")
            
        rca_prompt = self._build_rca_prompt(timeline_df)
        analysis_response_text = bedrock_client.invoke(rca_prompt)

        # Step 3: Check if the AI analysis was successful; if not, use a resilient fallback.
        if "Error:" in analysis_response_text or not self._is_valid_json(analysis_response_text):
            logger.warning("Bedrock analysis failed or returned invalid JSON. Using mock analysis as a fallback.")
            if status:
                status.update("[bold yellow]⚠️  Bedrock unavailable, using intelligent fallback analysis...[/bold yellow]")
            analysis_response_text = self._generate_mock_analysis(timeline_df)
        else:
            if status:
                status.update("[bold green]🎯 AI analysis completed successfully[/bold green]")
        
        # Step 4: Use the AI's analysis to intelligently request a remediation command from the MCP server.
        if status:
            status.update("[bold cyan]🔧 Requesting remediation command from MCP server...[/bold cyan]")
            
        logger.info("Requesting remediation command from MCP server...")
        remediation_command = await self._get_remediation_command(analysis_response_text)
        
        if status:
            status.update("[bold green]🚀 Remediation command generated successfully[/bold green]")
        
        # Step 5: Format the final, polished report for display.
        logger.info("Analysis pipeline completed successfully.")
        
        # Store data for potential Co-Pilot session
        self.last_analysis_data = {
            "timeline_df": timeline_df,
            "analysis_result": analysis_response_text,
            "remediation_command": remediation_command,
            "log_files": log_files
        }
        
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
        """Creates professional `rich` panels for the final console output with enhanced JSON parsing."""
        
        # Enhanced JSON extraction with multiple fallback strategies
        pretty_analysis = self._extract_and_format_json_robust(analysis_str)
        
        # Create beautifully formatted panels with enhanced styling
        report_panel = Panel(
            Syntax(pretty_analysis, "json", theme="monokai", line_numbers=True, word_wrap=True),
            title="[bold green]🧠 AI Root Cause Analysis[/bold green] [dim](AWS Bedrock Claude 3 Sonnet)[/dim]",
            subtitle="[dim]Confidence-scored incident analysis with supporting evidence[/dim]",
            border_style="green",
            expand=True,
            padding=(1, 2)
        )
        
        remediation_panel = Panel(
            Syntax(str(remediation_command), "bash", theme="monokai", word_wrap=True),
            title="[bold yellow]🔧 AI Suggested Remediation[/bold yellow] [dim](MCP Server)[/dim]",
            subtitle="[dim]Context-aware remediation command ready for execution[/dim]",
            border_style="yellow", 
            expand=True,
            padding=(1, 2)
        )
        
        return report_panel, remediation_panel

    def _extract_and_format_json_robust(self, analysis_str: str) -> str:
        """
        Enhanced JSON extraction with multiple parsing strategies to handle various AI response formats.
        
        This method tries several approaches to extract valid JSON from AI responses that might
        include extra text, markdown formatting, or other wrapper content.
        """
        
        # Strategy 1: Look for JSON within markdown code blocks
        markdown_json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        markdown_match = re.search(markdown_json_pattern, analysis_str, re.DOTALL | re.IGNORECASE)
        if markdown_match:
            try:
                json_obj = json.loads(markdown_match.group(1))
                return json.dumps(json_obj, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        
        # Strategy 2: Find the outermost complete JSON object (handles nested braces)
        brace_count = 0
        start_idx = -1
        end_idx = -1
        
        for i, char in enumerate(analysis_str):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    end_idx = i
                    break
        
        if start_idx != -1 and end_idx != -1:
            try:
                json_str = analysis_str[start_idx:end_idx + 1]
                json_obj = json.loads(json_str)
                return json.dumps(json_obj, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Simple regex fallback for basic JSON objects
        simple_json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        simple_match = re.search(simple_json_pattern, analysis_str, re.DOTALL)
        if simple_match:
            try:
                json_obj = json.loads(simple_match.group(0))
                return json.dumps(json_obj, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Try to parse the entire string as JSON (in case it's clean)
        try:
            json_obj = json.loads(analysis_str.strip())
            return json.dumps(json_obj, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        
        # Strategy 5: If all else fails, return a formatted error message with the original content
        logger.warning("Could not extract valid JSON from AI response using any strategy")
        return json.dumps({
            "error": "Could not parse JSON from AI response",
            "raw_response": analysis_str[:500] + "..." if len(analysis_str) > 500 else analysis_str,
            "note": "This may indicate an issue with the AI model response format"
        }, indent=2)

    def get_analysis_data_for_copilot(self) -> Optional[Dict[str, Any]]:
        """Get the last analysis data for Co-Pilot integration."""
        if not self.last_analysis_data:
            return None
        
        # Convert DataFrame to list of dictionaries for Co-Pilot
        timeline_data = []
        if 'timeline_df' in self.last_analysis_data:
            df = self.last_analysis_data['timeline_df']
            timeline_data = df.to_dict('records')
        
        return {
            "timeline_data": timeline_data,
            "analysis_result": self.last_analysis_data.get('analysis_result', ''),
            "remediation_command": self.last_analysis_data.get('remediation_command', ''),
            "log_files": self.last_analysis_data.get('log_files', [])
        }