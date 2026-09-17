# ZeniTrade AI — Python backend Dockerfile
# NOTE: MetaTrader5 library is Windows-only. This image runs the backend in
# "demo mode" (no real broker) for development/testing. For production trading,
# run the backend natively on Windows 11 where MT5 is installed.
FROM python:3.13-slim

WORKDIR /app

# system deps for numpy/pandas/xgboost
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# create dirs for model + db persistence
RUN mkdir -p /app/models/backups /app/data
ENV DB_PATH=/app/data/zenitrade.db

EXPOSE 8000

# healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# bind 0.0.0.0 inside container; auth via ZENITRADE_API_TOKEN env
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
