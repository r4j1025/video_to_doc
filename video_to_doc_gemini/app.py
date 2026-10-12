"""Streamlit UI: upload a video -> Word document."""
import shutil
import uuid
from pathlib import Path

import streamlit as st

import llm_service
from document_generator import build_document
from transcription import transcribe_chunks
from video_processor import (
    SUPPORTED_EXTENSIONS,
    extract_audio_chunks,
    extract_frames,
    get_video_info,
)

BASE = Path(__file__).parent
TEMP = BASE / "temp"
OUTPUT = BASE / "output"
TEMP.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)

st.set_page_config(page_title="Video to Document", page_icon="📄")
st.title("📄 Video to Document")
st.caption("Upload a video and get a Word document with summary, steps and screenshots.")

missing = llm_service.missing_config()
if missing:
    st.error("Missing settings in .env: " + ", ".join(missing))
    st.stop()

with st.sidebar:
    st.header("Options")
    doc_type = st.selectbox("Document type", list(llm_service.DOC_TYPES))
    max_frames = st.slider("Max screenshots", 3, 25, 10)
    include_transcript = st.checkbox("Include full transcript", value=True)

uploaded = st.file_uploader(
    "Video file", type=[e.lstrip(".") for e in sorted(SUPPORTED_EXTENSIONS)]
)

if uploaded and st.button("Generate document", type="primary"):
    run_dir = TEMP / uuid.uuid4().hex
    run_dir.mkdir(parents=True)
    st.session_state.pop("result", None)

    try:
        video_path = run_dir / uploaded.name
        video_path.write_bytes(uploaded.getbuffer())

        with st.status("Processing...", expanded=True) as status:
            st.write("Reading video details")
            info = get_video_info(video_path)
            if not info["has_video"]:
                raise ValueError("No video stream found in this file.")
            if not info["has_audio"]:
                raise ValueError("No audio track found - there is nothing to transcribe.")
            st.write(
                f"Duration {llm_service.fmt_time(info['duration'])}, "
                f"{info['width']}x{info['height']}"
            )

            st.write("Extracting audio")
            chunks = extract_audio_chunks(video_path, run_dir / "audio")

            st.write("Capturing screenshots")
            frames = extract_frames(video_path, run_dir / "frames", max_frames)

            bar = st.progress(0.0, text="Transcribing audio")
            segments = transcribe_chunks(
                chunks, progress=lambda i, n: bar.progress(i / n, text=f"Transcribing part {i + 1} of {n}")
            )
            bar.progress(1.0, text="Transcription complete")
            if not segments:
                raise ValueError("The transcription came back empty (is there speech in the video?).")

            st.write("Writing documentation with the LLM")
            content = llm_service.generate_documentation(segments, info["duration"], doc_type)

            st.write("Building Word document")
            out_path = OUTPUT / f"{Path(uploaded.name).stem}_documentation.docx"
            build_document(content, frames, segments, out_path, uploaded.name, include_transcript)
            status.update(label="Done", state="complete")

        st.session_state["result"] = {
            "bytes": out_path.read_bytes(),
            "name": out_path.name,
            "title": content.get("title", ""),
        }
    except Exception as e:
        st.error(f"Something went wrong: {e}")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)  # remove temp video/audio/frames

if "result" in st.session_state:
    r = st.session_state["result"]
    st.success(f"Created: {r['title'] or r['name']}")
    st.download_button(
        "Download .docx",
        data=r["bytes"],
        file_name=r["name"],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
