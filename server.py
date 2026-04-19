#!/usr/bin/env python3
"""
Whisper STT Service -- faster-whisper edition.

OpenAI-kompatible API, Drop-in fuer den bisherigen openai-whisper-Server.
Endpunkte:
  GET  /health                       -- Healthcheck
  GET  /                             -- API-Info
  POST /v1/audio/transcriptions      -- Speech-to-Text (OpenAI-kompatibel)
  POST /v1/audio/translations        -- Audio -> Englisch (OpenAI-kompatibel)

Kompatibilitaet zur bisherigen API:
  - gleiche Routen
  - gleiche Form-Fields (file, model, language, prompt, response_format, temperature)
  - gleiche Response-Shape fuer json / text / verbose_json
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from faster_whisper import WhisperModel

# ----- Logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("whisper")

# ----- Konfiguration via ENV -----
MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")
NUM_WORKERS = int(os.getenv("WHISPER_NUM_WORKERS", "1"))
CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))  # 0 = automatisch

# Globale Model-Instanz -- einmaliges Laden beim Start
_model: Optional[WhisperModel] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Model beim Start einmalig laden, beim Shutdown freigeben."""
    global _model
    log.info(
        "Loading faster-whisper model=%s compute_type=%s device=%s",
        MODEL_NAME, COMPUTE_TYPE, DEVICE,
    )
    _model = WhisperModel(
        MODEL_NAME,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        num_workers=NUM_WORKERS,
        cpu_threads=CPU_THREADS,
    )
    log.info("Model loaded. Ready to serve.")
    yield
    log.info("Shutting down. Releasing model.")
    _model = None


app = FastAPI(
    title="Whisper STT Service",
    version="2.0.0",
    description="faster-whisper with OpenAI-compatible API",
    lifespan=lifespan,
)


# ----- Helpers -----
def _segments_to_dict(segments) -> list[dict[str, Any]]:
    """Konvertiert faster-whisper Segment-Generator zu dict-Liste."""
    out = []
    for seg in segments:
        out.append({
            "id": seg.id,
            "seek": seg.seek,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "tokens": list(seg.tokens) if seg.tokens else [],
            "temperature": seg.temperature,
            "avg_logprob": seg.avg_logprob,
            "compression_ratio": seg.compression_ratio,
            "no_speech_prob": seg.no_speech_prob,
        })
    return out


def _transcribe(
    tmp_path: str,
    *,
    task: str,
    language: Optional[str],
    prompt: Optional[str],
    temperature: float,
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Fuehrt Transkription aus und gibt (full_text, segments, info) zurueck."""
    if _model is None:
        raise RuntimeError("Model not loaded yet")

    kwargs: dict[str, Any] = {
        "task": task,
        "temperature": temperature,
        "beam_size": 5,
        "vad_filter": True,  # VAD filtert Silence -- deutlich schneller
    }
    if language and language.lower() != "auto":
        kwargs["language"] = language
    if prompt:
        kwargs["initial_prompt"] = prompt

    segments_iter, info = _model.transcribe(tmp_path, **kwargs)

    # Generator ausrollen -> Text + Segments
    segments = _segments_to_dict(segments_iter)
    full_text = "".join(seg["text"] for seg in segments).strip()

    info_dict = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "duration_after_vad": info.duration_after_vad,
    }
    return full_text, segments, info_dict


# ----- Endpunkte -----
@app.get("/health")
async def health():
    """Healthcheck -- wird vom Docker-Healthcheck und Traefik abgefragt."""
    return {
        "status": "ok" if _model is not None else "loading",
        "model": MODEL_NAME,
        "compute_type": COMPUTE_TYPE,
        "device": DEVICE,
    }


@app.get("/")
async def root():
    """API-Info."""
    return {
        "name": "Whisper STT Service",
        "version": "2.0.0",
        "engine": "faster-whisper",
        "model": MODEL_NAME,
        "compute_type": COMPUTE_TYPE,
        "device": DEVICE,
        "default_language": DEFAULT_LANGUAGE,
        "endpoints": {
            "health": "/health",
            "transcribe": "/v1/audio/transcriptions",
            "translate": "/v1/audio/translations",
        },
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(MODEL_NAME),  # noqa: ARG001  -- fuer OpenAI-Compat akzeptiert, aber ignoriert
    language: Optional[str] = Form(None),
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
):
    """OpenAI-kompatible Transcription."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    suffix = os.path.splitext(file.filename)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text, segments, info = _transcribe(
            tmp_path,
            task="transcribe",
            language=language or DEFAULT_LANGUAGE,
            prompt=prompt,
            temperature=temperature,
        )
        log.info(
            "transcribe done: lang=%s duration=%.1fs segments=%d",
            info["language"], info["duration"], len(segments),
        )

        if response_format == "text":
            return PlainTextResponse(content=text)
        if response_format == "verbose_json":
            return JSONResponse(content={
                "task": "transcribe",
                "language": info["language"],
                "duration": info["duration"],
                "text": text,
                "segments": segments,
            })
        # default: json
        return JSONResponse(content={"text": text})

    except Exception as exc:  # noqa: BLE001
        log.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/v1/audio/translations")
async def translate(
    file: UploadFile = File(...),
    model: str = Form(MODEL_NAME),  # noqa: ARG001
    prompt: Optional[str] = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
):
    """OpenAI-kompatible Translation (Audio -> Englisch)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    suffix = os.path.splitext(file.filename)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text, segments, info = _transcribe(
            tmp_path,
            task="translate",
            language=None,  # Translate laesst Whisper Source-Language auto-detecten
            prompt=prompt,
            temperature=temperature,
        )
        log.info(
            "translate done: detected_lang=%s duration=%.1fs segments=%d",
            info["language"], info["duration"], len(segments),
        )

        if response_format == "text":
            return PlainTextResponse(content=text)
        if response_format == "verbose_json":
            return JSONResponse(content={
                "task": "translate",
                "language": info["language"],
                "duration": info["duration"],
                "text": text,
                "segments": segments,
            })
        return JSONResponse(content={"text": text})

    except Exception as exc:  # noqa: BLE001
        log.exception("Translation failed")
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
