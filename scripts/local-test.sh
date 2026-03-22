#!/bin/bash
echo "🧪 Starting Clarity locally..."
docker-compose up -d
echo "Waiting for API..."
until curl -sf http://localhost:8000/health > /dev/null; do sleep 2; done
echo "✅ Clarity is running!"
echo "  API:  http://localhost:8000"
echo "  Web:  http://localhost:3000"
echo "  Demo: http://localhost:3000#demo"
