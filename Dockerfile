FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first for better caching
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip install -e .

# Copy application code
COPY clarity/ /app/clarity/

# Expose standard MCP server port
EXPOSE 8001

# Run the MCP server by default
CMD ["python", "-m", "clarity", "start-mcp"]
