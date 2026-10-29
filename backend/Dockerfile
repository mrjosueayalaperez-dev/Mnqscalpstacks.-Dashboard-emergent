# Portable image for Railway / Fly.io / any container host (Render uses render.yaml).
# Build from the backend/ directory:  docker build -t mnq-backend backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .

EXPOSE 8000
# Single worker on purpose: in-memory engine state + background loops (see docs/MIGRATION.md).
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
