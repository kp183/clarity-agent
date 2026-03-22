"""
Co-Pilot Agent — Interactive investigation and knowledge transfer.

Provides natural language Q&A about incidents, helping engineers
understand root causes and learn from AI analysis.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from rich.panel import Panel
from rich.console import Console
from rich.prompt import Prompt
from rich.markdown import Markdown

from .base import BaseAgent
from ..core import logger
from ..core.llm_client import llm_client


@dataclass
class ConversationContext:
    """State maintained during a Co-Pilot session."""
    incident_data: Dict[str, Any] = field(default_factory=dict)
    timeline_data: List[Dict[str, Any]] = field(default_factory=list)
    analysis_result: str = ""
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    session_start: datetime = field(default_factory=datetime.now)
    # Richer context fields
    error_clusters: Dict[str, int] = field(default_factory=dict)
    service_topology: List[str] = field(default_factory=list)

    def enrich(self):
        """Build richer context from raw timeline data."""
        if not self.timeline_data:
            return
        # Cluster errors by service
        for event in self.timeline_data:
            if event.get("level", "").upper() in ("ERROR", "FATAL"):
                svc = event.get("service", "unknown")
                self.error_clusters[svc] = self.error_clusters.get(svc, 0) + 1
        # Extract unique services in order of appearance
        seen = set()
        for event in self.timeline_data:
            svc = event.get("service", "")
            if svc and svc not in seen:
                seen.add(svc)
                self.service_topology.append(svc)


class CoPilotAgent(BaseAgent):
    """Interactive investigation assistant for incident Q&A."""

    name = "Co-Pilot Agent"
    role = "Technical mentor and investigation assistant"
    goal = "Help engineers understand incidents and learn from analysis"

    def __init__(self):
        super().__init__()
        self.context: Optional[ConversationContext] = None

    async def run(self, incident_data, timeline_data, analysis_result):
        """Start interactive session. Alias for start_interactive_session."""
        self.start_interactive_session(incident_data, timeline_data, analysis_result)

    def start_interactive_session(
        self,
        incident_data: Dict[str, Any],
        timeline_data: List[Dict[str, Any]],
        analysis_result: str,
    ) -> None:
        """Launch the interactive Q&A terminal session."""
        self.context = ConversationContext(
            incident_data=incident_data,
            timeline_data=timeline_data,
            analysis_result=analysis_result,
        )
        self.context.enrich()

        console = Console()

        # Welcome message
        console.print(Panel(
            """🤖 **Co-Pilot Agent Activated**

I'm here to help you investigate this incident. Try asking:

• "Show me all database errors"
• "What happened right before the service went down?"
• "Explain the root cause in simple terms"
• "What could we have done to prevent this?"
• "Show me the timeline of events"

Type **exit** or **quit** to end.""",
            title="[bold cyan]💬 Interactive Investigation Mode[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(1, 2),
        ))
        console.print()

        # Chat loop
        while True:
            try:
                question = Prompt.ask(
                    "[bold cyan]🤔 Ask about this incident[/bold cyan]",
                    default="",
                )
                if not question or question.lower() in ("exit", "quit", "bye"):
                    break

                answer = self._process_question(question)
                self._display_answer(question, answer, console)

                self.context.conversation_history.append({
                    "question": question,
                    "answer": answer,
                    "timestamp": datetime.now().isoformat(),
                })

            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        self._end_session(console)

    # ─── Question Processing ─────────────────────

    def _process_question(self, question: str) -> str:
        try:
            prompt = self._build_qa_prompt(question)
            response = llm_client.invoke(prompt)

            if "Error:" in response:
                logger.warning("AI Q&A failed, using rule-based response")
                return self._rule_based_answer(question)

            return self._clean_response(response)
        except Exception as e:
            logger.error("Error processing question", error=str(e))
            return self._rule_based_answer(question)

    def _build_qa_prompt(self, question: str) -> str:
        timeline_summary = self._summarize_timeline()

        recent = ""
        if self.context.conversation_history:
            for qa in self.context.conversation_history[-2:]:
                recent += f"Q: {qa['question']}\nA: {qa['answer'][:200]}...\n\n"

        # Richer context
        error_summary = ""
        if self.context.error_clusters:
            error_summary = "ERROR DISTRIBUTION BY SERVICE:\n"
            for svc, count in sorted(self.context.error_clusters.items(), key=lambda x: -x[1]):
                error_summary += f"  - {svc}: {count} errors\n"

        topology = ""
        if self.context.service_topology:
            topology = f"SERVICES INVOLVED (order of appearance): {', '.join(self.context.service_topology)}\n"

        return f"""You are a Co-Pilot AI helping an engineer investigate an IT incident.

INCIDENT ANALYSIS:
{self.context.analysis_result}

{error_summary}
{topology}
TIMELINE DATA:
{timeline_summary}

RECENT CONVERSATION:
{recent}

QUESTION: {question}

Instructions:
- Answer directly and concisely
- Reference specific log entries with timestamps
- When discussing errors, mention which service and how many errors it had
- Provide chronological details for timeline questions
- Give actionable recommendations for prevention questions
- Say clearly if the question can't be answered from available data

Answer:"""

    def _summarize_timeline(self) -> str:
        if not self.context.timeline_data:
            return "No timeline data available."

        lines = []
        for event in self.context.timeline_data[:20]:
            ts = event.get("timestamp", "Unknown")
            lvl = event.get("level", "INFO")
            svc = event.get("service", "unknown")
            msg = event.get("message", "")[:100]
            lines.append(f"{ts} [{lvl}] {svc}: {msg}")
        return "\n".join(lines)

    def _clean_response(self, response: str) -> str:
        response = re.sub(r'```[a-zA-Z]*\n?', '', response)
        response = re.sub(r'\n?```', '', response)
        response = re.sub(r'\n\s*\n', '\n\n', response)
        return response.strip()

    # ─── Rule-Based Fallback ─────────────────────

    def _rule_based_answer(self, question: str) -> str:
        q = question.lower()

        if any(w in q for w in ("timeline", "sequence", "order", "when")):
            return self._timeline_answer()
        if any(w in q for w in ("error", "errors", "failed", "failure")):
            return self._error_answer()
        if any(w in q for w in ("cause", "why", "reason", "root")):
            return self._root_cause_answer()
        if any(w in q for w in ("prevent", "avoid", "stop", "future")):
            return self._prevention_answer()

        return f"""I understand you're asking: "{question}"

I can help you with:
- Timeline of events and sequence analysis
- Error patterns and failure analysis
- Root cause explanations
- Prevention recommendations

Could you rephrase to focus on one of these areas?"""

    def _timeline_answer(self) -> str:
        if not self.context.timeline_data:
            return "No timeline data available."

        events = []
        for e in self.context.timeline_data[:10]:
            lvl = e.get("level", "INFO")
            if lvl.upper() in ("ERROR", "WARN", "FATAL"):
                events.append(f"• {e.get('timestamp', '?')} [{lvl}] {e.get('message', '')}")

        if events:
            return "Key events from the timeline:\n\n" + "\n".join(events)
        return "Timeline shows mostly informational events. No critical errors found."

    def _error_answer(self) -> str:
        if not self.context.timeline_data:
            return "No log data available for error analysis."

        errors = []
        for e in self.context.timeline_data:
            if e.get("level", "").upper() == "ERROR":
                errors.append(f"• {e.get('timestamp', '?')}: {e.get('message', '')}")

        if errors:
            shown = errors[:5]
            result = f"Found {len(errors)} error events.\n\n" + "\n".join(shown)
            if len(errors) > 5:
                result += f"\n\n... and {len(errors) - 5} more"
            return result
        return "No ERROR level events found."

    def _root_cause_answer(self) -> str:
        analysis = self.context.analysis_result
        if "root_cause" in analysis.lower():
            for line in analysis.split("\n"):
                if "root_cause" in line.lower() or "description" in line.lower():
                    return f"Based on the analysis: {line.strip()}"

        return ("The analysis suggests issues related to service connectivity and availability. "
                "Deeper investigation of error patterns is recommended.")

    def _prevention_answer(self) -> str:
        return """Based on this incident pattern:

🔧 **Immediate Actions:**
• Implement connection pool monitoring
• Add circuit breakers for external service calls
• Set up proactive alerts for error rate thresholds

📊 **Monitoring Improvements:**
• Monitor database connection health continuously
• Track service response times and error rates
• Automated health checks for critical services

🏗️ **Architecture Enhancements:**
• Retry logic with exponential backoff
• Redundancy for critical dependencies
• Graceful degradation for service failures"""

    # ─── Display ─────────────────────────────────

    def _display_answer(self, question: str, answer: str, console: Console) -> None:
        console.print(Panel(
            Markdown(answer),
            title="[bold green]💡 Answer[/bold green]",
            subtitle=f"[dim]Q: {question}[/dim]",
            border_style="green",
            expand=True,
            padding=(1, 2),
        ))
        console.print()

    def _end_session(self, console: Console) -> None:
        duration = datetime.now() - self.context.session_start
        count = len(self.context.conversation_history)

        console.print(Panel(
            f"""🎯 **Session Complete**

Duration: {duration.total_seconds():.0f}s
Questions: {count}

Thank you for using Co-Pilot!""",
            title="[bold cyan]📋 Session Summary[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(1, 2),
        ))

        logger.info("Co-Pilot session ended", duration=duration.total_seconds(), questions=count)

    def export_conversation(self) -> Dict[str, Any]:
        if not self.context:
            return {}
        return {
            "session_start": self.context.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "questions_count": len(self.context.conversation_history),
            "history": self.context.conversation_history,
        }
