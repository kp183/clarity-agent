"""
Sentinel Agent — Proactive monitoring and predictive alerting.

Continuously scans log sources for anomalies and predicts incidents
before they occur using pattern detection and AI analysis.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from .base import BaseAgent
from ..core import logger
from ..core.models import (
    TrendType, AlertSeverity, TrendAnalysis, ProactiveAlert, MonitoringResult,
)
from ..config import settings
from ..parsers.log_parser import parse_log_files


class SentinelAgent(BaseAgent):
    """Proactive monitoring agent — detects trends and predicts incidents."""

    name = "Sentinel Agent"
    role = "Proactive monitoring specialist focused on preventing incidents"
    goal = "Detect negative trends and patterns that could lead to outages"

    def __init__(self):
        super().__init__()
        self.is_monitoring = False
        self.scan_count = 0
        self.interval = settings.monitoring_interval_seconds

    async def run(self, log_sources: List[str], status=None):
        """Start continuous monitoring. Alias for start_monitoring."""
        await self.start_monitoring(log_sources, status)

    async def start_monitoring(self, log_sources: List[str], status=None) -> None:
        """Continuously monitor log sources for anomalies."""
        self.is_monitoring = True
        logger.info("Sentinel starting monitoring...", sources=log_sources)

        if status:
            status.update("[bold green]🛡️ Sentinel activated[/bold green]")

        try:
            while self.is_monitoring:
                self.scan_count += 1
                if status:
                    status.update(f"[bold blue]🔍 Scan #{self.scan_count}...[/bold blue]")

                try:
                    result = await self._scan(log_sources, status)
                    self._display_results(result)

                    if result.trends_detected:
                        self._display_alerts(result.trends_detected)

                    if status:
                        next_time = (datetime.now() + timedelta(seconds=self.interval)).strftime("%H:%M:%S")
                        status.update(f"[bold green]✅ Scan #{self.scan_count} done. Next: {next_time}[/bold green]")
                except Exception as e:
                    logger.error("Scan iteration error", error=str(e))

                await asyncio.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user.")
        except Exception as e:
            logger.error("Monitoring error", error=str(e))
        finally:
            self.is_monitoring = False

    async def _scan(self, log_sources: List[str], status=None) -> MonitoringResult:
        """Perform a single monitoring scan cycle."""
        try:
            if status:
                status.update("[bold blue]📊 Analyzing log state...[/bold blue]")

            timeline_df = parse_log_files(log_sources)

            if timeline_df.empty:
                return MonitoringResult(
                    events_processed=0,
                    status="no_data",
                    scan_number=self.scan_count,
                )

            if status:
                status.update("[bold yellow]🧠 Detecting patterns...[/bold yellow]")

            trends = self._detect_trends(timeline_df)

            return MonitoringResult(
                events_processed=len(timeline_df),
                trends_detected=trends,
                status="success",
                scan_number=self.scan_count,
            )

        except Exception as e:
            logger.error("Scan error", error=str(e))
            return MonitoringResult(status=f"error: {e}", scan_number=self.scan_count)

    def _detect_trends(self, df) -> List[ProactiveAlert]:
        """Pattern-based trend detection with AI predictive analysis."""
        alerts: List[ProactiveAlert] = []

        try:
            if "level" not in df.columns:
                return alerts

            error_count = len(df[df["level"].str.upper() == "ERROR"])
            total = len(df)

            # Rule-based threshold check
            if total > 0:
                error_rate = error_count / total

                if error_rate > settings.alert_threshold_error_rate:
                    trend = TrendAnalysis(
                        metric_name="error_rate",
                        current_value=error_rate,
                        baseline_value=0.05,
                        trend_direction="increasing",
                        confidence=0.85,
                        time_window_minutes=5,
                        data_points=[],
                    )
                    alert = ProactiveAlert(
                        trend_type=TrendType.INCREASING_ERRORS,
                        severity=AlertSeverity.CRITICAL if error_rate > 0.25 else AlertSeverity.HIGH,
                        affected_services=list(df[df["level"].str.upper() == "ERROR"]["service"].dropna().unique()) if "service" in df.columns else ["unknown"],
                        description=f"High error rate detected: {error_rate:.0%}",
                        trend_data=trend,
                        recommended_actions=[
                            "Investigate error patterns in affected services",
                            "Check connectivity and dependencies",
                            "Review recent deployments",
                        ],
                    )
                    alerts.append(alert)

            # AI Predictive Analysis for hidden patterns (if we have enough data to analyze)
            if total > 5:
                ai_alerts = self._run_predictive_analysis(df)
                alerts.extend(ai_alerts)

        except Exception as e:
            logger.error("Trend detection error", error=str(e))

        return alerts

    def _run_predictive_analysis(self, df) -> List[ProactiveAlert]:
        """Use LLM to predict potential outages before they happen."""
        from ..core.llm_client import llm_client
        import json
        import re

        log_data = df.tail(30).to_string(index=False)

        prompt = f"""You are Sentinel Agent, a proactive monitoring AI.
Analyze the following recent log events and predict if there's a hidden, emerging issue that simple error thresholds might miss (e.g., slow degradation, cascading failures, subtle memory leaks).
If you find a hidden issue, describe it. If everything looks mostly stable, return "safe".
Return ONLY a valid JSON object. No markdown.

JSON Schema:
{{
    "issue_detected": true/false,
    "severity": "medium", // low/medium/high/critical
    "description": "Short explanation of the predicted issue",
    "affected_services": ["service-a"],
    "recommended_actions": ["Action 1", "Action 2"],
    "confidence": 0.8
}}

LOG DATA:
{log_data}"""

        try:
            response = llm_client.invoke(prompt)
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                if data.get("issue_detected"):
                    
                    # Map severity string to enum
                    sev_str = data.get("severity", "medium").lower()
                    sev_enum = AlertSeverity.MEDIUM
                    for s in AlertSeverity:
                        if s.value == sev_str:
                            sev_enum = s
                            break

                    trend = TrendAnalysis(
                        metric_name="ai_prediction",
                        current_value=1.0,
                        baseline_value=0.0,
                        trend_direction="anomalous",
                        confidence=data.get("confidence", 0.7),
                        time_window_minutes=15,
                        data_points=[]
                    )
                    
                    return [ProactiveAlert(
                        trend_type=TrendType.PERFORMANCE_DEGRADATION,
                        severity=sev_enum,
                        affected_services=data.get("affected_services", ["unknown"]),
                        description=data.get("description", "AI detected an anomalous pattern"),
                        trend_data=trend,
                        recommended_actions=data.get("recommended_actions", ["Investigate immediately"])
                    )]
        except Exception as e:
            logger.warning("Predictive analysis failed", error=str(e))
            
        return []

    def _display_results(self, result: MonitoringResult) -> None:
        """Display scan results as a Rich table."""
        console = Console()
        table = Table(title=f"🛡️ Sentinel Scan #{result.scan_number}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Scan Time", result.scan_time.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("Events Processed", str(result.events_processed))
        table.add_row("Trends Detected", str(len(result.trends_detected)))
        table.add_row("Status", result.status)

        console.print(table)

    def _display_alerts(self, alerts: List[ProactiveAlert]) -> None:
        """Display proactive alerts."""
        console = Console()

        for alert in alerts:
            content = f"""🚨 PROACTIVE ALERT

Trend: {alert.trend_type.value}
Severity: {alert.severity.value.upper()}
Confidence: {alert.trend_data.confidence:.1%}
Description: {alert.description}

Affected Services: {', '.join(alert.affected_services)}

Recommended Actions:
{chr(10).join(f'• {a}' for a in alert.recommended_actions)}
"""
            color_map = {
                AlertSeverity.LOW: "yellow",
                AlertSeverity.MEDIUM: "orange3",
                AlertSeverity.HIGH: "red",
                AlertSeverity.CRITICAL: "bright_red",
            }
            color = color_map.get(alert.severity, "yellow")

            console.print(Panel(
                content,
                title=f"[bold {color}]⚠️ {alert.severity.value.upper()} ALERT[/bold {color}]",
                border_style=color,
                expand=True,
                padding=(1, 2),
            ))

    def stop(self):
        """Stop monitoring."""
        self.is_monitoring = False
        logger.info("Sentinel monitoring stopped.")
