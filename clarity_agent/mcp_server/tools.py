from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
# Correctly import the logger from its new location in the package
from ..utils.logging import logger

# Initialize FastAPI server for MCP-style tool serving
mcp_server = FastAPI(title="Clarity Agent Remediation Tools", version="1.0.0")

# --- Pydantic models for structured input (No changes needed here) ---
class ServiceCommand(BaseModel):
    service_name: str
    namespace: str = "default"
    
class ScaleCommand(ServiceCommand):
    replicas: int

# --- Tool Definitions using FastAPI endpoints ---

@mcp_server.post("/tools/rollback")
def get_rollback_command(request: ServiceCommand) -> Dict[str, Any]:
    """Generate kubectl rollback command for a service deployment."""
    service_name = request.service_name
    namespace = request.namespace
    
    if not service_name or not service_name.strip():
        raise HTTPException(status_code=400, detail="Service name cannot be empty")
    
    # Sanitize inputs to prevent command injection
    safe_service = "".join(c for c in service_name if c.isalnum() or c == '-')
    safe_namespace = "".join(c for c in namespace if c.isalnum() or c == '-')
    
    command = f"kubectl rollout undo deployment/{safe_service} -n {safe_namespace}"
    
    logger.info("Generated rollback command", 
                service=safe_service, 
                namespace=safe_namespace, 
                command=command)
    
    return {
        "tool": "rollback",
        "command": command,
        "service": safe_service,
        "namespace": safe_namespace
    }

@mcp_server.post("/tools/restart")
def get_restart_command(request: ServiceCommand) -> Dict[str, Any]:
    """Generate kubectl restart command for a service deployment."""
    service_name = request.service_name
    namespace = request.namespace
    
    if not service_name or not service_name.strip():
        raise HTTPException(status_code=400, detail="Service name cannot be empty")
    
    safe_service = "".join(c for c in service_name if c.isalnum() or c == '-')
    safe_namespace = "".join(c for c in namespace if c.isalnum() or c == '-')
    
    command = f"kubectl rollout restart deployment/{safe_service} -n {safe_namespace}"
    
    logger.info("Generated restart command", 
                service=safe_service, 
                namespace=safe_namespace, 
                command=command)
    
    return {
        "tool": "restart",
        "command": command,
        "service": safe_service,
        "namespace": safe_namespace
    }

@mcp_server.post("/tools/scale")
def get_scale_command(request: ScaleCommand) -> Dict[str, Any]:
    """Generate kubectl scale command for a service deployment."""
    service_name = request.service_name
    namespace = request.namespace
    replicas = request.replicas
    
    if not service_name or not service_name.strip():
        raise HTTPException(status_code=400, detail="Service name cannot be empty")
    
    if replicas < 0:
        raise HTTPException(status_code=400, detail="Replicas must be non-negative")
    
    safe_service = "".join(c for c in service_name if c.isalnum() or c == '-')
    safe_namespace = "".join(c for c in namespace if c.isalnum() or c == '-')
    
    command = f"kubectl scale deployment/{safe_service} --replicas={replicas} -n {safe_namespace}"
    
    logger.info("Generated scale command", 
                service=safe_service, 
                replicas=replicas,
                namespace=safe_namespace, 
                command=command)
    
    return {
        "tool": "scale",
        "command": command,
        "service": safe_service,
        "namespace": safe_namespace,
        "replicas": replicas
    }

@mcp_server.post("/tools/validate")
def validate_service_exists(request: ServiceCommand) -> Dict[str, Any]:
    """Simulates validating that a service exists in a Kubernetes cluster."""
    service_name = request.service_name
    namespace = request.namespace
    
    if not service_name or not service_name.strip():
        exists = False
    else:
        # Simulate a list of known, valid services for the demo
        common_services = ["auth-service", "api-service", "user-service", "payment-service"]
        exists = service_name in common_services
    
    logger.info("Validating service existence", 
                service=service_name, 
                namespace=namespace,
                exists=exists)
    
    return {
        "tool": "validate",
        "service": service_name,
        "namespace": namespace,
        "exists": exists
    }

# Add a health check endpoint
@mcp_server.get("/health")
def health_check():
    """Health check endpoint for the MCP server."""
    return {"status": "healthy", "service": "Clarity Agent MCP Server"}

# Add a tools list endpoint
@mcp_server.get("/tools")
def list_tools():
    """List all available tools."""
    return {
        "tools": [
            {"name": "rollback", "endpoint": "/tools/rollback", "description": "Generate kubectl rollback command"},
            {"name": "restart", "endpoint": "/tools/restart", "description": "Generate kubectl restart command"},
            {"name": "scale", "endpoint": "/tools/scale", "description": "Generate kubectl scale command"},
            {"name": "validate", "endpoint": "/tools/validate", "description": "Validate service existence"}
        ]
    }