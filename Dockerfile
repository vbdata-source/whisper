# syntax=docker/dockerfile:1.7
# =============================================================================
# Whisper STT Service -- faster-whisper edition
# =============================================================================
# API-kompatibel zu openai-whisper, aber:
#   - 3-4x schneller auf CPU
#   - ~3.5 GB Peak-RAM statt ~10 GB (dank int8-Quantisierung)
#   - Modell ins Image gebaken: kein Runtime-Download
# =============================================================================

# ---------- Builder-Stage: Wheels installieren + Modell vorladen ----------
FROM python:3.11-slim AS builder

ARG MODEL_NAME=large-v3
ARG COMPUTE_TYPE=int8

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        build-essential \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-Dependencies. faster-whisper bringt CTranslate2 + HF-Hub mit.
RUN pip install --upgrade pip && \
    pip install \
        faster-whisper==1.1.1 \
        fastapi==0.115.0 \
        "uvicorn[standard]==0.30.6" \
        python-multipart==0.0.12 \
        requests==2.32.3

# Modell-Preload: laedt large-v3 in int8 ins HuggingFace-Cache des Builders.
# Wird dann in der finalen Stage uebernommen -> kein Runtime-Download noetig.
RUN python -c "from faster_whisper import WhisperModel; \
               WhisperModel('${MODEL_NAME}', device='cpu', compute_type='${COMPUTE_TYPE}')"


# ---------- Runtime-Stage: schlank & logging-ready ----------
FROM python:3.11-slim

ARG MODEL_NAME=large-v3
ARG COMPUTE_TYPE=int8

# PYTHONUNBUFFERED ist Pflicht: ohne diese Zeile sind die Logs unsichtbar,
# wenn der Container crasht (stdout-Buffer wird bei SIGKILL nicht geflusht).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WHISPER_MODEL=${MODEL_NAME} \
    WHISPER_COMPUTE_TYPE=${COMPUTE_TYPE} \
    WHISPER_LANGUAGE=de

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python-Packages + HF-Cache (Modell!) aus der Builder-Stage uebernehmen
COPY --from=builder /usr/local/lib/python3.11/site-packages \
                    /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

WORKDIR /app
COPY server.py .

EXPOSE 8000

# start_period: 60s reicht jetzt locker - Modell ist im Image, nicht im Cache
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
