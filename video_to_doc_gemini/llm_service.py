"""Gemini access: one client, one function to build the documentation."""
import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DOC_TYPES = {
    "How-to guide / tutorial": (
        "Write a step-by-step how-to guide. Each section covers one task or stage of the "
        "video and lists the concrete actions the presenter performs, in order."
    ),
    "Meeting / training notes": (
        "Write structured notes. Each section covers one topic discussed, with the key "
        "points, decisions and action items as the steps."
    ),
    "General summary": (
        "Write a clear summary document. Each section covers one topic, with the main "
        "points as the steps."
    ),
}


def missing_config():
    needed = ["GEMINI_API_KEY", "GEMINI_MODEL"]
    return [k for k in needed if not os.getenv(k)]


def get_client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def fmt_time(seconds):
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}" if s < 3600 else f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def transcript_text(segments):
    return "\n".join(f"[{fmt_time(s['start'])}] {s['text']}" for s in segments)


def generate_documentation(segments, duration, doc_type):
    """Ask the LLM for structured documentation. Returns a dict."""
    system = (
        "You turn video transcripts into clear professional documentation. "
        "Use only information present in the transcript; do not invent details. "
        "Reply with a single JSON object and nothing else."
    )
    user = f"""{DOC_TYPES[doc_type]}

The video is {fmt_time(duration)} long. The transcript has [mm:ss] timestamps.

Return JSON with exactly this shape:
{{
  "title": "short document title",
  "summary": "3-5 sentence overview",
  "key_topics": ["topic", "..."],
  "sections": [
    {{
      "heading": "section title",
      "start_seconds": 0,
      "explanation": "1-3 sentence explanation of this section",
      "steps": ["step or key point", "..."]
    }}
  ]
}}

Rules: sections must be in chronological order; start_seconds is the number of seconds
into the video where the section begins; use 4-12 sections depending on length.

TRANSCRIPT:
{transcript_text(segments)}
"""
    client = get_client()
    resp = client.models.generate_content(
        model=os.environ["GEMINI_MODEL"],
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
        ),
    )
    return json.loads(resp.text)
