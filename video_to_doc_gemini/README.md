# Video to Document

Upload a local video -> get a Word document (summary, sections, steps, screenshots, transcript).

## Setup
```
python -m venv .venv
.venv\Scripts\activate          # Windows
python -m pip install -r requirements.txt
copy .env.example .env          # then fill in your Gemini API key
streamlit run app.py
```

## Pipeline
1. `video_processor.py` - PyAV reads metadata, decodes audio to 16 kHz mono WAV chunks, saves screenshots
2. `transcription.py`  - local OpenAI Whisper (CPU) transcribes each chunk (timestamps preserved)
3. `llm_service.py`    - Gemini (google-genai) turns the transcript into structured JSON
4. `document_generator.py` - python-docx builds the .docx (screenshots matched to section timestamps)
5. `app.py` - Streamlit UI; temp files are deleted after each run, the .docx is saved in `output/`

## Notes
- No ffmpeg/ffprobe executables, no subprocess calls, no YouTube. PyAV wheels bundle FFmpeg *libraries*; confirm with the client that this is acceptable.
- Needs a Gemini API key (model set by `GEMINI_MODEL`, default `gemini-3.5-flash-lite`; one request per video). Whisper runs locally; nothing but the transcript text leaves the machine.
- Whisper: the `openai-whisper` package (installs PyTorch, a large download). The model (`WHISPER_MODEL` in `.env`, default `base`) downloads into `whisper_models/` on the first run, then loads from there and stays in memory while the app runs. Audio is passed to Whisper as an array, so no ffmpeg executable is needed.
- Videos with no speech cannot be documented (the document is built from the transcript).
