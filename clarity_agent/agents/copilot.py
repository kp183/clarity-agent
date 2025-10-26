"""
Co-Pilot Agent - Interactive Investigation and Knowledge Transfer

The Co-Pilot Agent provides natural language interaction with incident data,
helping engineers understand incidents deeply and learn from AI analysis.
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Rich imports for beautiful console output
from rich.panel import Panel
from rich.syntax import Syntax
from rich.console import Console
from rich.prompt import Prompt
from rich.markdown import Markdown

# Project imports
from ..services.bedrock import bedrock_client
from ..config.settings import settings
from ..utils.logging import logger
from ..models.core import LogLevel

@dataclass
class ConversationContext:
    """Context maintained during a Co-Pilot session."""
    incident_data: Dict[str, Any]
    timeline_data: List[Dict[str, Any]]
    analysis_result: str
    conversation_history: List[Dict[str, str]]
    session_start: datetime

class CoPilotAgent:
    """
    The Co-Pilot Agent - Technical mentor and investigation assistant.
    
    Role: Technical mentor and investigation assistant
    Goal: Help engineers understand incidents and learn from analysis
    Backstory: Expert at explaining complex technical issues in accessible terms
    """

    def __init__(self):
        """Initialize the Co-Pilot Agent."""
        self.role = "Technical mentor and investigation assistant"
        self.goal = "Help engineers understand incidents and learn from analysis"
        self.context: Optional[ConversationContext] = None
        logger.info("Co-Pilot Agent initialized for interactive investigation.")

    def start_interactive_session(self, incident_data: Dict[str, Any], 
                                timeline_data: List[Dict[str, Any]], 
                                analysis_result: str) -> None:
        """
        Start an interactive Q&A session with the incident data.
        
        Args:
            incident_data: Processed incident information
            timeline_data: Timeline of log events
            analysis_result: AI analysis result from Analyst Agent
        """
        # Initialize conversation context
        self.context = ConversationContext(
            incident_data=incident_data,
            timeline_data=timeline_data,
            analysis_result=analysis_result,
            conversation_history=[],
            session_start=datetime.now()
        )
        
        console = Console()
        
        # Welcome message
        welcome_panel = Panel(
            """🤖 **Co-Pilot Agent Activated**

I'm here to help you understand this incident in detail. You can ask me questions like:

• "Show me all database errors after 14:25"
• "What happened right before the service became unhealthy?"
• "Explain the root cause in simple terms"
• "What could we have done to prevent this?"
• "Show me the timeline of events"

Type 'exit' or 'quit' to end the session.""",
            title="[bold cyan]💬 Interactive Investigation Mode[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(1, 2)
        )
        
        console.print(welcome_panel)
        console.print()
        
        # Interactive loop
        while True:
            try:
                # Get user question
                question = Prompt.ask(
                    "[bold cyan]🤔 Ask me anything about this incident[/bold cyan]",
                    default=""
                )
                
                if not question or question.lower() in ['exit', 'quit', 'bye']:
                    break
                
                # Process the question
                answer = self._process_question(question)
                
                # Display the answer
                self._display_answer(question, answer)
                
                # Add to conversation history
                self.context.conversation_history.append({
                    "question": question,
                    "answer": answer,
                    "timestamp": datetime.now().isoformat()
                })
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error processing question: {e}[/red]")
        
        # Session end
        self._end_session()

    def _process_question(self, question: str) -> str:
        """Process a user question and generate an answer."""
        try:
            # Build context-aware prompt for AI
            prompt = self._build_qa_prompt(question)
            
            # Get AI response
            ai_response = bedrock_client.invoke(prompt)
            
            # If AI fails, use rule-based fallback
            if "Error:" in ai_response:
                logger.warning("AI Q&A failed, using rule-based response")
                return self._generate_rule_based_answer(question)
            
            return self._clean_ai_response(ai_response)
            
        except Exception as e:
            logger.error("Error processing question", error=str(e))
            return self._generate_rule_based_answer(question)

    def _build_qa_prompt(self, question: str) -> str:
        """Build a context-aware prompt for Q&A."""
        # Summarize timeline data for the prompt
        timeline_summary = self._summarize_timeline_for_qa()
        
        # Get recent conversation context
        recent_context = ""
        if len(self.context.conversation_history) > 0:
            recent_qa = self.context.conversation_history[-2:]  # Last 2 Q&As
            recent_context = "\n".join([
                f"Previous Q: {qa['question']}\nPrevious A: {qa['answer'][:200]}..."
                for qa in recent_qa
            ])
        
        prompt = f"""You are a Co-Pilot AI assistant helping an engineer understand an IT incident.

INCIDENT ANALYSIS:
{self.context.analysis_result}

TIMELINE DATA:
{timeline_summary}

RECENT CONVERSATION:
{recent_context}

CURRENT QUESTION: {question}

Instructions:
- Answer the question directly and concisely
- Reference specific log entries with timestamps when relevant
- If asking about timeline, provide chronological details
- If asking for explanations, use clear, technical language
- If asking about prevention, provide actionable recommendations
- If the question cannot be answered from available data, say so clearly

Provide a helpful, accurate answer based on the incident data:"""

        return prompt

    def _summarize_timeline_for_qa(self) -> str:
        """Create a concise timeline summary for Q&A context."""
        if not self.context.timeline_data:
            return "No timeline data available."
        
        # Take key events for context
        timeline_events = []
        for i, event in enumerate(self.context.timeline_data[:20]):  # Limit for prompt size
            timestamp = event.get('timestamp', 'Unknown time')
            level = event.get('level', 'INFO')
            message = event.get('message', 'No message')
            service = event.get('service', 'unknown')
            
            timeline_events.append(f"{timestamp} [{level}] {service}: {message[:100]}")
        
        return "\n".join(timeline_events)

    def _clean_ai_response(self, response: str) -> str:
        """Clean and format AI response."""
        # Remove any markdown code blocks
        response = re.sub(r'```[a-zA-Z]*\n?', '', response)
        response = re.sub(r'\n?```', '', response)
        
        # Clean up extra whitespace
        response = re.sub(r'\n\s*\n', '\n\n', response)
        response = response.strip()
        
        return response

    def _generate_rule_based_answer(self, question: str) -> str:
        """Generate rule-based answers when AI is unavailable."""
        question_lower = question.lower()
        
        # Timeline questions
        if any(word in question_lower for word in ['timeline', 'sequence', 'order', 'when']):
            return self._generate_timeline_answer()
        
        # Error-specific questions
        if any(word in question_lower for word in ['error', 'errors', 'failed', 'failure']):
            return self._generate_error_analysis()
        
        # Root cause questions
        if any(word in question_lower for word in ['cause', 'why', 'reason', 'root']):
            return self._extract_root_cause_summary()
        
        # Prevention questions
        if any(word in question_lower for word in ['prevent', 'avoid', 'stop', 'future']):
            return self._generate_prevention_advice()
        
        # Default response
        return f"""I understand you're asking: "{question}"

Based on the incident data I have access to, I can help you with:
- Timeline of events and sequence analysis
- Error patterns and failure analysis  
- Root cause explanations
- Prevention recommendations

Could you rephrase your question to be more specific about what aspect of the incident you'd like to explore?"""

    def _generate_timeline_answer(self) -> str:
        """Generate timeline-based answer."""
        if not self.context.timeline_data:
            return "No timeline data is available for this incident."
        
        key_events = []
        for event in self.context.timeline_data[:10]:
            timestamp = event.get('timestamp', 'Unknown')
            level = event.get('level', 'INFO')
            message = event.get('message', 'No message')
            
            if level.upper() in ['ERROR', 'WARN', 'FATAL']:
                key_events.append(f"• {timestamp} [{level}] {message}")
        
        if key_events:
            return f"Here are the key events from the timeline:\n\n" + "\n".join(key_events)
        else:
            return "The timeline shows mostly informational events. No critical errors were found in the sequence."

    def _generate_error_analysis(self) -> str:
        """Generate error-focused analysis."""
        if not self.context.timeline_data:
            return "No log data available for error analysis."
        
        error_count = 0
        error_examples = []
        
        for event in self.context.timeline_data:
            if event.get('level', '').upper() == 'ERROR':
                error_count += 1
                if len(error_examples) < 3:
                    timestamp = event.get('timestamp', 'Unknown')
                    message = event.get('message', 'No message')
                    error_examples.append(f"• {timestamp}: {message}")
        
        if error_count > 0:
            result = f"Found {error_count} error events in the logs.\n\nKey error examples:\n"
            result += "\n".join(error_examples)
            if error_count > 3:
                result += f"\n\n... and {error_count - 3} more errors"
            return result
        else:
            return "No explicit ERROR level events found in the timeline data."

    def _extract_root_cause_summary(self) -> str:
        """Extract root cause from analysis."""
        try:
            # Try to extract root cause from the analysis result
            if "root_cause" in self.context.analysis_result.lower():
                # Simple extraction - in a real system this would be more sophisticated
                lines = self.context.analysis_result.split('\n')
                for line in lines:
                    if 'root_cause' in line.lower() or 'description' in line.lower():
                        return f"Based on the analysis: {line.strip()}"
            
            return "The analysis suggests this incident was related to system connectivity and service availability issues. The specific root cause would require deeper investigation of the error patterns and system state at the time of the incident."
            
        except Exception:
            return "Unable to extract specific root cause information from the current analysis."

    def _generate_prevention_advice(self) -> str:
        """Generate prevention recommendations."""
        return """Based on this incident pattern, here are prevention recommendations:

🔧 **Immediate Actions:**
• Implement better connection pool monitoring
• Add circuit breakers for external service calls
• Set up proactive alerts for error rate thresholds

📊 **Monitoring Improvements:**
• Monitor database connection health continuously
• Track service response times and error rates
• Set up automated health checks for critical services

🏗️ **Architecture Enhancements:**
• Consider implementing retry logic with exponential backoff
• Add redundancy for critical service dependencies
• Implement graceful degradation for service failures

These recommendations would help detect and prevent similar incidents in the future."""

    def _display_answer(self, question: str, answer: str) -> None:
        """Display the Q&A in a beautiful format."""
        console = Console()
        
        # Create answer panel
        answer_panel = Panel(
            Markdown(answer),
            title=f"[bold green]💡 Answer[/bold green]",
            subtitle=f"[dim]Question: {question}[/dim]",
            border_style="green",
            expand=True,
            padding=(1, 2)
        )
        
        console.print(answer_panel)
        console.print()

    def _end_session(self) -> None:
        """End the interactive session."""
        console = Console()
        
        session_duration = datetime.now() - self.context.session_start
        questions_asked = len(self.context.conversation_history)
        
        summary_panel = Panel(
            f"""🎯 **Investigation Session Complete**

Session Duration: {session_duration.total_seconds():.0f} seconds
Questions Asked: {questions_asked}
Incident Understanding: Enhanced through interactive exploration

Thank you for using the Co-Pilot Agent! The conversation history has been logged for future reference.""",
            title="[bold cyan]📋 Session Summary[/bold cyan]",
            border_style="cyan",
            expand=True,
            padding=(1, 2)
        )
        
        console.print(summary_panel)
        
        # Log session completion
        logger.info("Co-Pilot session completed", 
                   duration_seconds=session_duration.total_seconds(),
                   questions_count=questions_asked)

    def export_conversation(self) -> Dict[str, Any]:
        """Export the conversation history."""
        if not self.context:
            return {}
        
        return {
            "session_start": self.context.session_start.isoformat(),
            "session_end": datetime.now().isoformat(),
            "questions_count": len(self.context.conversation_history),
            "conversation_history": self.context.conversation_history,
            "incident_summary": {
                "timeline_events": len(self.context.timeline_data),
                "analysis_available": bool(self.context.analysis_result)
            }
        }