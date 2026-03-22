"""
FastAPI REST API to serve Clarity features to the web dashboard.
"""

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends, Security, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import shutil
import asyncio
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from ..agents.analyst import AnalystAgent
from ..agents.sentinel import SentinelAgent
from ..agents.copilot import CoPilotAgent
from ..core import logger
from ..config import settings

import json as _json
from pathlib import Path
import tempfile
import uuid

# ─── Sentry (optional) ───────────────────────────────────────────────────────
if os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        traces_sample_rate=0.1,
    )
    logger.info("✅ Sentry error monitoring initialized.")

# ─── Rate limiter ─────────────────────────────────────────────────────────────
# Note: default uses in-memory storage (single instance only).
# For multi-instance production use Redis:
#   Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6379")
limiter = Limiter(key_func=get_remote_address)

# ─── JWT auth ────────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> None:
    """Validate a Bearer JWT when AUTH_ENABLED is True.

    Raises HTTP 401 if the token is missing or invalid.
    Does nothing when ``settings.auth_enabled`` is False.
    """
    if not settings.auth_enabled:
        return

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        from jose import jwt, JWTError  # python-jose
        jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

app = FastAPI(
    title="Clarity API",
    description="REST API backend for Clarity Web Dashboard",
    version="1.0.0",
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Enable CORS for the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage keyed by session_id for concurrent request isolation
_memory_state: Dict[str, Dict[str, Any]] = {}
_session_order: List[str] = []  # tracks insertion order for "most recent" fallback
_trial_usage: Dict[str, int] = {}


def _get_session(session_id: str) -> Dict[str, Any]:
    """Return the state dict for a session, creating it if needed."""
    if session_id not in _memory_state:
        _memory_state[session_id] = {"copilot_data": None, "last_analysis": None}
        _session_order.append(session_id)
    return _memory_state[session_id]


def _latest_session() -> Optional[Dict[str, Any]]:
    """Return the most recently created session state, or None."""
    if not _session_order:
        return None
    return _memory_state.get(_session_order[-1])

class DemoRequest(BaseModel):
    scenario: str  # 'db_pool', 'memory_leak', 'deployment_bug'

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    history: List[Dict[str, str]]

class TicketResponse(BaseModel):
    ticket_markdown: str


@app.on_event("startup")
async def startup_check():
    """Verify critical config on startup."""
    provider = settings.llm_provider
    if provider == "groq" and not settings.groq_api_key:
        logger.error("Missing required env var: GROQ_API_KEY")
        raise RuntimeError("Missing GROQ_API_KEY — set it in .env")
    if provider == "bedrock" and not settings.aws_profile_name:
        logger.error("Missing AWS configuration")
        raise RuntimeError("Missing AWS configuration")
    logger.info(f"✅ Startup checks passed. LLM provider: {provider}")


@app.get("/health")
def health_check():
    """Health check for the API."""
    return {"status": "healthy", "service": "Clarity REST API"}


@app.post("/demo/analyze")
async def analyze_demo(req: DemoRequest):
    """Analyze a pre-loaded demo scenario — no auth required."""
    demo_files = {
        "db_pool": "demo_data/db_pool_incident.log",
        "memory_leak": "demo_data/memory_leak_incident.log",
        "deployment_bug": "demo_data/deployment_bug.log",
    }
    meta_files = {
        "db_pool": "demo_data/db_pool_incident.json",
        "memory_leak": "demo_data/memory_leak_incident.json",
        "deployment_bug": "demo_data/deployment_bug.json",
    }
    if req.scenario not in demo_files:
        raise HTTPException(status_code=400, detail=f"Invalid scenario. Choose from: {list(demo_files.keys())}")

    log_file = demo_files[req.scenario]
    if not Path(log_file).exists():
        raise HTTPException(status_code=404, detail=f"Demo file not found: {log_file}")

    with open(meta_files[req.scenario]) as f:
        metadata = _json.load(f)

    agent = AnalystAgent()
    await agent.run_analysis([log_file])
    copilot_data = agent.get_analysis_data_for_copilot()

    analysis_str = copilot_data.get("analysis_result", "{}") if copilot_data else "{}"
    try:
        import re
        match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
        parsed = _json.loads(match.group(0)) if match else _json.loads(analysis_str)
    except Exception:
        parsed = {"raw": analysis_str}

    return {
        "demo": True,
        "scenario": req.scenario,
        "metadata": metadata,
        "analysis": parsed,
        "remediation_command": copilot_data.get("remediation_command") if copilot_data else None,
    }


@app.post("/analyze")
@limiter.limit("10/minute")
async def analyze_logs(request: Request, files: List[UploadFile] = File(...), _: None = Depends(verify_token)):
    """Upload log files and run reactive analysis."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    temp_dir = tempfile.mkdtemp()
    saved_files = []
    
    try:
        # Trial limit check
        client_ip = request.client.host if request.client else "unknown"
        usage = _trial_usage.get(client_ip, 0)
        if usage >= 100:  # Generous trial - roughly 1 month of real usage
            raise HTTPException(
                status_code=403,
                detail="You've used all 100 free analyses. Install the CLI for unlimited local usage: pip install clarity-ai",
            )

        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)

        agent = AnalystAgent()
        await agent.run_analysis(saved_files)
        
        copilot_data = agent.get_analysis_data_for_copilot()
        session_id = str(uuid.uuid4())
        session = _get_session(session_id)
        session["copilot_data"] = copilot_data
        session["last_analysis"] = agent.last_analysis_data

        if copilot_data and "analysis_result" in copilot_data:
            import json
            import re
            
            analysis_str = copilot_data["analysis_result"]
            try:
                match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
                if match:
                    parsed_result = json.loads(match.group(0))
                else:
                    parsed_result = json.loads(analysis_str)
            except Exception:
                parsed_result = {"raw": analysis_str}

            _trial_usage[client_ip] = usage + 1
            trial_remaining = max(0, 100 - _trial_usage[client_ip])
            return {
                "status": "success",
                "session_id": session_id,
                "analysis": parsed_result,
                "remediation_command": copilot_data.get("remediation_command"),
                "trial_remaining": trial_remaining,
            }
            
        return {"status": "success", "session_id": session_id, "message": "Analysis completed, but no formatted result was returned."}

    except Exception as e:
        logger.error("Analysis failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in saved_files:
            try:
                os.remove(path)
            except:
                pass
        try:
            os.rmdir(temp_dir)
        except:
            pass


@app.post("/ticket", response_model=TicketResponse)
async def generate_ticket(x_session_id: Optional[str] = Header(default=None), _: None = Depends(verify_token)):
    """Generate a markdown ticket from the last analysis."""
    if x_session_id:
        session = _memory_state.get(x_session_id)
    else:
        session = _latest_session()
    if not session:
        raise HTTPException(status_code=400, detail="No recent analysis available.")
    data = session["copilot_data"]
    if not data:
        raise HTTPException(status_code=400, detail="No recent analysis available.")
        
    analysis_str = data.get("analysis_result", "")
    remediation_cmd = data.get("remediation_command", "")
    
    import json
    import re
    import datetime
    
    try:
        json_match = re.search(r'\{.*\}', analysis_str, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            parsed = {"summary": "Analysis data unavailable"}
    except:
        parsed = {"summary": "Analysis parsing error"}

    components = "\n".join(f"• {c}" for c in parsed.get("affected_components", ["unknown"]))
    
    ticket_md = f"""### 🤖 AI-Powered Incident Report

**Summary:** {parsed.get('summary', 'N/A')}

**Root Cause Analysis:**
{parsed.get('root_cause_description', 'N/A')}

**Affected Components:**
{components}

**AI Confidence Score:** {parsed.get('confidence_score', 0.0):.1%}

**Recommended Remediation:**
```bash
{remediation_cmd}
```

**Analysis Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
    return TicketResponse(ticket_markdown=ticket_md)


@app.post("/copilot/chat", response_model=ChatResponse)
@limiter.limit("30/minute")
async def chat_with_copilot(request: Request, req: ChatRequest, x_session_id: Optional[str] = Header(default=None), _: None = Depends(verify_token)):
    """Interact with the Co-Pilot using natural language."""
    if x_session_id:
        session = _memory_state.get(x_session_id)
    else:
        session = _latest_session()
    if not session:
        raise HTTPException(status_code=400, detail="No active incident context. Please run analysis first.")
    data = session["copilot_data"]
    if not data:
        raise HTTPException(status_code=400, detail="No active incident context. Please run analysis first.")

    agent = CoPilotAgent()
    import datetime
    from ..agents.copilot import ConversationContext

    agent.context = ConversationContext()
    agent.context.incident_data = {}
    agent.context.timeline_data = data.get("timeline_data", [])
    agent.context.analysis_result = data.get("analysis_result", "")
    agent.context.conversation_history = session.get("chat_history", [])
    agent.context.session_start = datetime.datetime.now() if not session.get("chat_history") else None
    
    answer = agent._process_question(req.message)
    
    if "chat_history" not in session:
        session["chat_history"] = []
        
    session["chat_history"].append({
        "question": req.message,
        "answer": answer,
        "timestamp": datetime.datetime.now().isoformat()
    })
    
    return ChatResponse(
        reply=answer,
        history=session["chat_history"]
    )


@app.get("/monitoring/status")
async def get_monitoring_status(_: None = Depends(verify_token)):
    """Trigger a quick sentinel scan and return anomalies."""
    agent = SentinelAgent()
    target_logs = ["./logs/app_errors.log", "./logs/deployment_logs.json"]
    
    available_logs = [f for f in target_logs if os.path.exists(f)]
    if not available_logs:
        return {"status": "no_data", "message": "No log files found to monitor."}
        
    result = await agent._scan(available_logs)
    
    if result.status != "success":
        return {"status": result.status, "message": "Scan returned non-success state"}

    abnormal_trends = []
    if result.trends_detected:
         for a in result.trends_detected:
              abnormal_trends.append({
                  "type": a.trend_type.value,
                  "severity": a.severity.value,
                  "description": a.description,
                  "affected_services": a.affected_services,
                  "actions": a.recommended_actions
              })
              
    return {
        "status": result.status,
        "events_processed": result.events_processed,
        "abnormal_trends": abnormal_trends
    }
