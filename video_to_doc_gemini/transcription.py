"""Local transcription with OpenAI Whisper (openai-whisper package).

The model is downloaded into ./whisper_models on the first run, then loaded from
there and kept in memory for every later video. The audio is passed to Whisper as a
numpy array, so Whisper never needs an ffmpeg executable.
"""
import os
import wave
from pathlib import Path

import numpy as np
import whisper

MODEL_DIR = Path(__file__).parent / "whisper_models"
_model = None


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(
            os.getenv("WHISPER_MODEL", "base"),
            download_root=str(MODEL_DIR),
        )
    return _model


def _load_wav(path):
    """Read a 16 kHz mono 16-bit WAV (made by video_processor) as float32 in [-1, 1]."""
    with wave.open(str(path), "rb") as w:
        pcm = w.readframes(w.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def transcribe_chunks(chunks, progress=None):
    """Transcribe WAV chunks. Returns [{"start": s, "end": s, "text": str}] on the
    full video's timeline."""
    model = get_model()
    language = os.getenv("WHISPER_LANGUAGE") or None  # e.g. "en"; empty = auto-detect
    segments = []

    for i, chunk in enumerate(chunks):
        if progress:
            progress(i, len(chunks))
        result = model.transcribe(_load_wav(chunk["path"]), language=language, fp16=False)
        for seg in result["segments"]:
            text = seg["text"].strip()
            if text:
                segments.append({
                    "start": chunk["offset"] + seg["start"],
                    "end": chunk["offset"] + seg["end"],
                    "text": text,
                })

    return segments
