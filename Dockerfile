FROM python:3.11-slim AS builder

ARG MODEL_NAME=large-v3

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir openai-whisper fastapi uvicorn python-multipart

RUN python -c "import whisper; whisper.load_model('${MODEL_NAME}')"

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/whisper /root/.cache/whisper

WORKDIR /app
COPY server.py .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
