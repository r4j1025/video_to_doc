"""Video handling with PyAV only: metadata, audio extraction, screenshots.

No ffmpeg/ffprobe executables and no subprocess calls are used.
"""
import wave
from pathlib import Path

import av

SAMPLE_RATE = 16000          # Whisper's native rate
AUDIO_CHUNK_SECONDS = 600    # 10 min of 16 kHz mono WAV ~ 19 MB per chunk
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def get_video_info(video_path):
    """Return duration, resolution and stream availability."""
    with av.open(str(video_path)) as container:
        video = container.streams.video[0] if container.streams.video else None
        has_audio = len(container.streams.audio) > 0
        duration = float(container.duration / av.time_base) if container.duration else 0.0
        return {
            "duration": duration,
            "width": video.codec_context.width if video else 0,
            "height": video.codec_context.height if video else 0,
            "has_video": video is not None,
            "has_audio": has_audio,
        }


def extract_frames(video_path, out_dir, max_frames=10):
    """Save evenly spaced screenshots. Returns [{"time": seconds, "path": str}]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []

    with av.open(str(video_path)) as container:
        stream = container.streams.video[0]
        duration = float(container.duration / av.time_base) if container.duration else 0.0
        count = max(1, max_frames)
        interval = duration / count if duration else 1.0
        # aim for the middle of each slice so we skip black intro frames
        targets = [interval * (i + 0.5) for i in range(count)]

        for i, target in enumerate(targets):
            container.seek(int(target / stream.time_base), stream=stream)
            chosen = None
            for frame in container.decode(stream):
                if frame.pts is None:
                    continue
                chosen = frame
                if float(frame.pts * stream.time_base) >= target:
                    break
            if chosen is None:
                continue

            t = float(chosen.pts * stream.time_base)
            img = chosen.to_image()
            img.thumbnail((1280, 720))
            path = out_dir / f"frame_{i:03d}.jpg"
            img.save(path, quality=85)
            frames.append({"time": t, "path": str(path)})

    return frames


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _write_wav(path, pcm):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(pcm))


def extract_audio_chunks(video_path, out_dir):
    """Decode audio to 16 kHz mono WAV, split into chunks small enough for the
    transcription API. Returns [{"path": str, "offset": seconds}]."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    max_bytes = AUDIO_CHUNK_SECONDS * SAMPLE_RATE * 2  # 16-bit samples
    state = {"buf": bytearray(), "written": 0}

    def flush():
        if not state["buf"]:
            return
        path = out_dir / f"audio_{len(chunks):03d}.wav"
        _write_wav(path, state["buf"])
        chunks.append({"path": str(path), "offset": state["written"] / (SAMPLE_RATE * 2)})
        state["written"] += len(state["buf"])
        state["buf"] = bytearray()

    def add(resampled_frames):
        for rf in _as_list(resampled_frames):
            state["buf"] += bytes(rf.planes[0])[: rf.samples * 2]
            if len(state["buf"]) >= max_bytes:
                flush()

    with av.open(str(video_path)) as container:
        if not container.streams.audio:
            return []
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(stream):
            add(resampler.resample(frame))
        add(resampler.resample(None))  # flush resampler

    flush()
    return chunks
