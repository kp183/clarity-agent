"""
MCP Server — Remediation tool endpoints.

Provides kubectl command generation for automated incident remediation.
Served as a FastAPI application with input sanitization and security checks.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from ..core import logger


# ─── FastAPI App ─────────────────────────────────

mcp_app = FastAPI(
    title="Clarity Remediation Tools",
    description="MCP-compatible tool server for automated incident remediation",
    version="1.0.0",
)


# ─── Request Models ──────────────────────────────

class ServiceCommand(BaseModel):
    service_name: str
    namespace: str = "default"

class ScaleCommand(ServiceCommand):
    replicas: int


# ─── Helpers ─────────────────────────────────────

def _sanitize(value: str) -> str:
    """Remove dangerous characters from input."""
    return "".join(c for c in value if c.isalnum() or c == "-")


def _validate_service(name: str):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Service name cannot be empty")


# ─── Tool Endpoints ─────────────────────────────

@mcp_app.post("/tools/rollback")
def rollback(req: ServiceCommand) -> Dict[str, Any]:
    """Generate kubectl rollback command."""
    _validate_service(req.service_name)
    svc = _sanitize(req.service_name)
    ns = _sanitize(req.namespace)
    cmd = f"kubectl rollout undo deployment/{svc} -n {ns}"
    logger.info("Generated rollback command", service=svc, command=cmd)
    return {"tool": "rollback", "command": cmd, "service": svc, "namespace": ns}


@mcp_app.post("/tools/restart")
def restart(req: ServiceCommand) -> Dict[str, Any]:
    """Generate kubectl restart command."""
    _validate_service(req.service_name)
    svc = _sanitize(req.service_name)
    ns = _sanitize(req.namespace)
    cmd = f"kubectl rollout restart deployment/{svc} -n {ns}"
    logger.info("Generated restart command", service=svc, command=cmd)
    return {"tool": "restart", "command": cmd, "service": svc, "namespace": ns}


@mcp_app.post("/tools/scale")
def scale(req: ScaleCommand) -> Dict[str, Any]:
    """Generate kubectl scale command."""
    _validate_service(req.service_name)
    if req.replicas < 0:
        raise HTTPException(status_code=400, detail="Replicas must be non-negative")
    svc = _sanitize(req.service_name)
    ns = _sanitize(req.namespace)
    cmd = f"kubectl scale deployment/{svc} --replicas={req.replicas} -n {ns}"
    logger.info("Generated scale command", service=svc, replicas=req.replicas, command=cmd)
    return {"tool": "scale", "command": cmd, "service": svc, "namespace": ns, "replicas": req.replicas}


@mcp_app.post("/tools/validate")
def validate(req: ServiceCommand) -> Dict[str, Any]:
    """Validate that a service exists (simulated)."""
    known = ["auth-service", "api-service", "user-service", "payment-service"]
    exists = req.service_name in known
    logger.info("Validated service", service=req.service_name, exists=exists)
    return {"tool": "validate", "service": req.service_name, "namespace": req.namespace, "exists": exists}


# ─── Utility Endpoints ──────────────────────────

@mcp_app.get("/health")
def health():
    return {"status": "healthy", "service": "Clarity MCP Server"}


@mcp_app.get("/tools")
def list_tools():
    return {
        "tools": [
            {"name": "rollback", "endpoint": "/tools/rollback", "description": "Generate kubectl rollback command"},
            {"name": "restart", "endpoint": "/tools/restart", "description": "Generate kubectl restart command"},
            {"name": "scale", "endpoint": "/tools/scale", "description": "Generate kubectl scale command"},
            {"name": "validate", "endpoint": "/tools/validate", "description": "Validate service existence"},
        ]
    }
