FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
RUN apt-get update && apt-get install -y ripgrep git && rm -rf /var/lib/apt/lists/*
COPY services/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/orchestrator/orchestrator ./orchestrator
CMD ["celery", "-A", "orchestrator.celery_app", "worker", "-l", "info"]
