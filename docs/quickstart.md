# Quickstart Guide

## Prerequisites

- Python 3.11+
- AWS account with Bedrock access (Amazon Titan model enabled)
- Node.js 18+ (for web dashboard)

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/clarity.git
cd clarity

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install in editable mode
pip install -e .

# Copy environment file
cp .env.example .env
# Edit .env with your AWS credentials and preferences
```

## CLI Usage

```bash
# Analyze log files
clarity analyze logs/app_errors.log logs/deployment_logs.json

# Start proactive monitoring
clarity monitor logs/app_errors.log --interval 15

# Generate an incident ticket
clarity ticket logs/app_errors.log

# Start the MCP remediation server
clarity start-mcp

# Start the REST API backend
clarity start-api --port 8000

# Check version
clarity version
```

## Web Dashboard

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:3000
```

Make sure the REST API backend is running (`clarity start-api`) for the dashboard to function.

## Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f clarity-mcp
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=clarity --cov-report=html
```
