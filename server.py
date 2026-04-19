#!/usr/bin/env python3
"""
OpenAI-compatible Whisper API Server
Provides /v1/audio/transcriptions endpoint
"""

import os
import tempfile
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import whisper

# Initialize
app = FastAPI(title="Whisper STT Service", version="1.0.0")

# Load Model
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")

print(f"Loading Whisper model: {MODEL_NAME}")
model = whisper.load_model(MODEL_NAME)
print(f"Model loaded successfully!")

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "model": MODEL_NAME}

@app.get("/")
async def root():
    """Root endpoint with API info"""
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
    """
    OpenAI-compatible transcription endpoint
    
    Compatible with:
    - n8n HTTP Request Node
    - OpenAI Whisper API clients
    - curl: curl -F file=@audio.mp3 -F model=large-v3 http://whisper:8000/v1/audio/transcriptions
    """
    
    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Transcribe
        options = {
            "language": language or DEFAULT_LANGUAGE,
            "temperature": temperature,
        }
        
        if prompt:
            options["initial_prompt"] = prompt
        
        result = model.transcribe(tmp_path, **options)
        
        # Format response based on response_format
        if response_format == "text":
            return result["text"]
        elif response_format == "verbose_json":
            return JSONResponse(content=result)
        else:  # json (default)
            return JSONResponse(content={"text": result["text"]})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.post("/v1/audio/translations")
async def translate(
    file: UploadFile = File(...),
    model: str = Form(MODEL_NAME),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0)
):
    """
    Translate audio to English (OpenAI-compatible)
    """
    
    if not file:
        raise HTTPException(status_code=400, detail="No audio file provided")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # Translate to English
        options = {
            "task": "translate",
            "temperature": temperature,
        }
        
        if prompt:
            options["initial_prompt"] = prompt
        
        result = model.transcribe(tmp_path, **options)
        
        # Format response
        if response_format == "text":
            return result["text"]
        elif response_format == "verbose_json":
            return JSONResponse(content=result)
        else:  # json (default)
            return JSONResponse(content={"text": result["text"]})
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")
    
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
