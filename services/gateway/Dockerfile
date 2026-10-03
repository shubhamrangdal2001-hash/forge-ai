FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
COPY services/gateway/requirements.txt ./gateway-requirements.txt
COPY services/orchestrator/requirements.txt ./orchestrator-requirements.txt
RUN pip install --no-cache-dir -r gateway-requirements.txt -r orchestrator-requirements.txt
COPY services/gateway/app ./app
COPY services/orchestrator/orchestrator ./orchestrator
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
