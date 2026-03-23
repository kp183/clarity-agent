FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip install -e .

COPY clarity/ /app/clarity/
COPY demo_data/ /app/demo_data/

EXPOSE 8000

CMD ["uvicorn", "clarity.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
