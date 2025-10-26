"""
Sentinel Agent - Proactive Monitoring and Trend Detection
"""
import asyncio
import pandas as pd
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Rich imports
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.console import Console

# Project imports
from ..utils.parsers import parse_log_files
from ..services.bedrock import bedrock_client
from ..config.settings import settings
from ..utils.logging import logger
from ..models.core import LogLevel
# Import all required models
from ..models.monitoring import ProactiveAlert, TrendAnalysis, TrendType, AlertSeverity

@dataclass
class MonitoringResult:
    """Result of a monitoring scan cycle."""
    scan_time: datetime
    events_processed: int
    trends_detected: List[ProactiveAlert]
    status: str
    next_scan: datetime

class SentinelAgent:
    """
    The Sentinel Agent - Proactive monitoring specialist focused on preventing incidents.
    """

    def __init__(self):
        """Initialize the Sentinel Agent with monitoring configuration."""
        self.role = "Proactive monitoring specialist focused on preventing incidents"
        self.goal = "Detect negative trends and patterns that could lead to outages"
        self.monitoring_interval = 30  # 30 seconds for demo purposes
        self.is_monitoring = False
        self.scan_count = 0
        logger.info("Sentinel Agent initialized for proactive monitoring.")

    async def start_monitoring(self, log_sources: List[str], status=None) -> None:
        """Start continuous proactive monitoring of log sources."""
        self.is_monitoring = True
        logger.info("Sentinel Agent starting proactive monitoring...", sources=log_sources)
        
        if status:
            status.update("[bold green]🛡️ Sentinel Agent activated - Starting proactive monitoring...[/bold green]")
        
        try:
            while self.is_monitoring:
                scan_start = datetime.now()
                self.scan_count += 1
                
                if status:
                    status.update(f"[bold blue]🔍 Performing monitoring scan #{self.scan_count}...[/bold blue]")
                
                # Perform monitoring scan
                result = await self._perform_monitoring_scan(log_sources, status)
                
                # Display results
                self._display_monitoring_results(result)
                
                # Check for alerts
                if result.trends_detected:
                    await self._handle_proactive_alerts(result.trends_detected, status)
                
                if status:
                    next_scan_time = (scan_start + timedelta(seconds=self.monitoring_interval)).strftime("%H:%M:%S")
                    status.update(f"[bold green]✅ Scan #{self.scan_count} complete. Next scan at {next_scan_time}[/bold green]")
                
                # Wait for next scan interval
                await asyncio.sleep(self.monitoring_interval)
                
        except KeyboardInterrupt:
            logger.info("Sentinel Agent monitoring stopped by user.")
            if status:
                status.update("[bold yellow]🛑 Monitoring stopped by user[/bold yellow]")
        except Exception as e:
            logger.error("Error in Sentinel Agent monitoring", error=str(e))
            if status:
                status.update(f"[bold red]❌ Monitoring error: {e}[/bold red]")
        finally:
            self.is_monitoring = False

    async def _perform_monitoring_scan(self, log_sources: List[str], status=None) -> MonitoringResult:
        """Perform a single monitoring scan cycle."""
        scan_time = datetime.now()
        
        try:
            if status:
                status.update("[bold blue]📊 Analyzing current log state...[/bold blue]")
                
            timeline_df = parse_log_files(log_sources)
            events_processed = len(timeline_df)
            
            if timeline_df.empty:
                return MonitoringResult(
                    scan_time=scan_time,
                    events_processed=0,
                    trends_detected=[],
                    status="no_data",
                    next_scan=scan_time + timedelta(seconds=self.monitoring_interval)
                )
            
            if status:
                status.update("[bold yellow]🧠 Analyzing trends and patterns...[/bold yellow]")
                
            trends = self._detect_trends_with_patterns(timeline_df)
            
            return MonitoringResult(
                scan_time=scan_time,
                events_processed=events_processed,
                trends_detected=trends,
                status="success",
                next_scan=scan_time + timedelta(seconds=self.monitoring_interval)
            )
            
        except Exception as e:
            logger.error("Error during monitoring scan", error=str(e))
            return MonitoringResult(
                scan_time=scan_time,
                events_processed=0,
                trends_detected=[],
                status=f"error: {e}",
                next_scan=scan_time + timedelta(seconds=self.monitoring_interval)
            )

    def _detect_trends_with_patterns(self, timeline_df) -> List[ProactiveAlert]:
        """Pattern-based trend detection for demo purposes."""
        alerts = []
        
        try:
            if 'level' in timeline_df.columns:
                # Check for ERROR level events (case-insensitive string comparison)
                error_count = len(timeline_df[timeline_df['level'].str.upper() == 'ERROR'])
                total_count = len(timeline_df)
                
                if total_count > 0:
                    error_rate = error_count / total_count
                    
                    # Lower threshold for demo - trigger alert if more than 10% errors
                    if error_rate > 0.10:
                        
                        # --- THE FIX IS HERE ---
                        # We must provide all required fields for the Pydantic models.
                        
                        trend_data = TrendAnalysis(
                            metric_name="error_rate",
                            current_value=error_rate,
                            baseline_value=0.05,
                            trend_direction="increasing",
                            confidence=0.85,
                            time_window_minutes=5,  # Added the missing field
                            data_points=[]
                        )
                        
                        alert = ProactiveAlert(
                            trend_type=TrendType.INCREASING_ERRORS,
                            severity=AlertSeverity.HIGH if error_rate > 0.25 else AlertSeverity.MEDIUM,
                            affected_services=["auth-service", "database"],
                            description=f"Detected a high error rate ({error_rate:.0%}) in system logs.", # Added missing field
                            trend_data=trend_data,
                            recommended_actions=[
                                "Investigate error patterns in auth-service",
                                "Check database connection health",
                                "Review recent deployments",
                            ]
                        )
                        alerts.append(alert)
                        
        except Exception as e:
            logger.error("Error in pattern-based trend detection", error=str(e))
        
        return alerts

    def _display_monitoring_results(self, result: MonitoringResult) -> None:
        """Display monitoring results in a beautiful format."""
        console = Console()
        table = Table(title=f"🛡️ Sentinel Monitoring Scan #{self.scan_count}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Scan Time", result.scan_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Events Processed", str(result.events_processed))
        table.add_row("Trends Detected", str(len(result.trends_detected)))
        table.add_row("Status", result.status)
        table.add_row("Next Scan", result.next_scan.strftime("%H:%M:%S"))
        
        console.print(table)

    async def _handle_proactive_alerts(self, alerts: List[ProactiveAlert], status=None) -> None:
        """Handle detected proactive alerts."""
        if not alerts:
            return
            
        console = Console()
        
        for alert in alerts:
            alert_content = f"""🚨 PROACTIVE ALERT DETECTED

Trend Type: {alert.trend_type.value}
Severity: {alert.severity.value.upper()}
Confidence: {alert.trend_data.confidence:.1%}
Description: {alert.description}

Affected Services: {', '.join(alert.affected_services)}

Recommended Actions:
{chr(10).join(f'• {action}' for action in alert.recommended_actions)}
"""
            
            panel_style = {
                AlertSeverity.LOW: "yellow",
                AlertSeverity.MEDIUM: "orange3", 
                AlertSeverity.HIGH: "red",
                AlertSeverity.CRITICAL: "bright_red"
            }.get(alert.severity, "yellow")
            
            alert_panel = Panel(
                alert_content,
                title=f"[bold {panel_style}]⚠️ PROACTIVE ALERT - {alert.severity.value.upper()}[/bold {panel_style}]",
                border_style=panel_style,
                expand=True,
                padding=(1, 2)
            )
            
            console.print(alert_panel)
            
            logger.warning("Proactive alert detected", 
                           trend_type=alert.trend_type.value,
                           severity=alert.severity.value,
                           confidence=alert.trend_data.confidence)

    def stop_monitoring(self) -> None:
        """Stop the monitoring process."""
        self.is_monitoring = False
        logger.info("Sentinel Agent monitoring stopped.")