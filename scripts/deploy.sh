#!/bin/bash
echo "🚀 Deploying Clarity..."
docker build -t clarity-api:latest .
docker build -t clarity-web:latest ./web
echo "✅ Images built. Push to your registry and deploy."
echo "  docker push your-registry/clarity-api:latest"
echo "  docker push your-registry/clarity-web:latest"
