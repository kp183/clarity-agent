# API Reference

## REST API Endpoints

Base URL: `http://localhost:8000`

### Health Check

```
GET /health
```

**Response:**
```json
{ "status": "healthy", "service": "Clarity REST API" }
```

---

### Analyze Logs

```
POST /analyze
Content-Type: multipart/form-data
```

**Parameters:**
| Name    | Type   | Description                    |
|---------|--------|--------------------------------|
| files   | File[] | One or more log files to analyze |

**Response:**
```json
{
  "status": "success",
  "analysis": {
    "summary": "Database connection timeout caused cascading failures",
    "root_cause_description": "Connection pool exhaustion in auth-service",
    "affected_components": ["auth-service", "user-service"],
    "confidence_score": 0.87,
    "remediation_steps": ["Restart the connection pool", "Scale replicas"]
  },
  "remediation_command": "kubectl rollout restart deployment/auth-service"
}
```

---

### Co-Pilot Chat

```
POST /copilot/chat
Content-Type: application/json
```

**Request Body:**
```json
{ "message": "What caused the auth-service failure?" }
```

**Response:**
```json
{
  "reply": "The auth-service failure was caused by...",
  "history": [
    {
      "question": "What caused the auth-service failure?",
      "answer": "The auth-service failure was caused by...",
      "timestamp": "2024-01-15T10:30:00"
    }
  ]
}
```

---

### Generate Ticket

```
POST /ticket
```

**Response:**
```json
{
  "ticket_markdown": "### 🤖 AI-Powered Incident Report\n\n..."
}
```

Requires a prior `/analyze` call to populate context.

---

### Monitoring Status

```
GET /monitoring/status
```

**Response:**
```json
{
  "status": "success",
  "events_processed": 150,
  "abnormal_trends": [
    {
      "type": "increasing_errors",
      "severity": "high",
      "description": "High error rate detected: 35%",
      "affected_services": ["auth-service"],
      "actions": ["Investigate error patterns"]
    }
  ]
}
```

---

## MCP Server Endpoints

Base URL: `http://localhost:8001`

### List Available Tools

```
GET /tools
```

### Rollback Service

```
POST /tools/rollback
{ "service_name": "auth-service", "namespace": "default" }
```

### Restart Service

```
POST /tools/restart
{ "service_name": "auth-service" }
```

### Scale Service

```
POST /tools/scale
{ "service_name": "auth-service", "replicas": 5 }
```

### Validate Service

```
POST /tools/validate
{ "service_name": "auth-service" }
```
