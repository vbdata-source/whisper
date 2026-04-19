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
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir openai-whisper fastapi uvicorn python-multipart

# Pre-download Whisper Model (spart Zeit beim ersten Start)
RUN python -c "import whisper; whisper.load_model('${MODEL_NAME}')"

# Runtime Stage
FROM python:3.11-slim

# Runtime Dependencies (nur ffmpeg + curl)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded model
COPY --from=builder /root/.cache/whisper /root/.cache/whisper

# Application Code (inline statt COPY)
WORKDIR /app
RUN cat > server.py << 'EOF'
#!/usr/bin/env python3
import os
import tempfile
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import whisper

app = FastAPI(title="Whisper STT Service", version="1.0.0")
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")

print(f"Loading Whisper model: {MODEL_NAME}")
model = whisper.load_model(MODEL_NAME)
print(f"Model loaded successfully!")

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}

@app.get("/")
async def root():
    return {
        "name": "Whisper STT Service",
        "model": MODEL_NAME,
        "endpoints": {
            "transcribe": "/v1/audio/transcriptions",
            "health": "/health"
        }
    }

@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(MODEL_NAME),
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0)
):
    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        options = {
            "language": language or DEFAULT_LANGUAGE,
            "temperature": temperature,
        }
        if prompt:
            options["initial_prompt"] = prompt
        
        result = model.transcribe(tmp_path, **options)
        
        if response_format == "text":
            return result["text"]
        elif response_format == "verbose_json":
            return JSONResponse(content=result)
        else:
            return JSONResponse(content={"text": result["text"]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Expose Port
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run Server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
