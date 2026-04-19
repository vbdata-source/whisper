# Multi-Stage Build für optimierte Image-Größe
FROM python:3.11-slim AS builder

# Build Args
ARG MODEL_NAME=large-v3

# System Dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python Dependencies
WORKDIR /app
COPY requirements.txt* ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir openai-whisper fastapi uvicorn python-multipart

# Pre-download Whisper Model (spart Zeit beim ersten Start)
RUN python -c "import whisper; whisper.load_model('${MODEL_NAME}')"

# Runtime Stage
FROM python:3.11-slim

# Runtime Dependencies (nur ffmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded model
COPY --from=builder /root/.cache/whisper /root/.cache/whisper

# Application Code
WORKDIR /app
COPY server.py .

# Expose Port
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run Server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
