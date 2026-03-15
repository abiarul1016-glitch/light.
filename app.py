import os
import re
import json
import uuid
import logging
import tempfile
from flask import Flask, request, jsonify, render_template, session
from flask_session import Session
import whisper
from openai import OpenAI, OpenAIError

# ─────────────────────────────────────────
# Logging
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────
# OpenAI-compatible client (HuggingFace OSS)
# ─────────────────────────────────────────
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "test"),
    base_url="https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
)

# ─────────────────────────────────────────
# Whisper  (loaded once at startup)
# ─────────────────────────────────────────
log.info("Loading Whisper model…")
whisper_model = whisper.load_model("turbo")
log.info("Whisper ready.")

# ─────────────────────────────────────────
# Flask + server-side sessions
# ─────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", uuid.uuid4().hex)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = tempfile.mkdtemp(prefix="light_sessions_")
app.config["SESSION_PERMANENT"] = False
Session(app)

# ─────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert fraud detection assistant specialising in Canadian phone scams.
You receive a phone call transcript and must return ONLY a valid JSON object — no markdown, no explanation, no extra text.

Common Canadian scam patterns to detect:
- Canada Revenue Agency (CRA) impersonation
- Service Canada / CERB / OAS / CPP fraud
- TD, RBC, Scotiabank, BMO impersonation
- RCMP / local police impersonation
- Threats of arrest or deportation
- Gift card / cryptocurrency payment demands
- Urgent SIN number requests
- Prize / lottery scams

Return this exact shape:
{
  "probability": <float 0-1>,
  "type": "<concise scam category or 'Legitimate call'>",
  "reasons": ["<why flagged 1>", "<why flagged 2>"],
  "questions": ["<verification question 1>", "<verification question 2>", "<verification question 3>"],
  "urgency": "<low|medium|high>"
}"""


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def _extract_content(resp) -> str:
    msg = resp.choices[0].message
    return (
        getattr(msg, "content", None)
        or getattr(msg, "reasoning", None)
        or ""
    ).strip()


def _parse_json_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    log.warning("Could not parse JSON from model response: %r", raw[:300])
    return {}


def _safe_defaults() -> dict:
    return {
        "probability": 0.5,
        "type": "Unknown",
        "reasons": ["Could not analyse transcript at this time."],
        "questions": [
            "Can you provide your official employee ID?",
            "What is the direct callback number for your department?",
            "I will call the official number from the website to verify.",
        ],
        "urgency": "medium",
    }


def _normalise(raw: dict) -> dict:
    try:
        prob = float(raw.get("probability", 0.5))
        prob = max(0.0, min(1.0, prob))
    except (TypeError, ValueError):
        prob = 0.5
    return {
        "probability": prob,
        "type":      str(raw.get("type", "Unknown")),
        "reasons":   list(raw.get("reasons", [])),
        "questions": list(raw.get("questions", [])),
        "urgency":   str(raw.get("urgency", "medium")),
    }


def analyze_transcript(transcript: str) -> dict:
    if not transcript.strip():
        return _safe_defaults()
    prompt = f"Analyze the following phone call transcript for scam indicators.\n\nTranscript:\n{transcript}"
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        raw = _extract_content(resp)
        log.debug("Raw model output: %s", raw)
        result = _parse_json_response(raw)
    except OpenAIError as exc:
        log.error("LLM request failed: %s", exc)
        return _safe_defaults()
    return _normalise(result)


# ─────────────────────────────────────────
# Routes
# ─────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze-chunk", methods=["POST"])
def analyze_chunk():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    suffix = os.path.splitext(audio_file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        audio_file.save(tmp_path)

    try:
        whisper_result = whisper_model.transcribe(tmp_path, language="en")
        chunk_text = whisper_result["text"].strip()
        log.info("Transcribed chunk (%d chars): %s…", len(chunk_text), chunk_text[:80])
    except Exception as exc:
        log.error("Whisper transcription failed: %s", exc)
        return jsonify({"error": "Transcription failed"}), 500
    finally:
        os.unlink(tmp_path)

    session.setdefault("transcript", "")
    session["transcript"] = (session["transcript"] + " " + chunk_text).strip()
    session.modified = True

    analysis = analyze_transcript(session["transcript"])

    return jsonify({
        "chunk":           chunk_text,
        "full_transcript": session["transcript"],
        "probability":     round(analysis["probability"] * 100, 1),
        "type":            analysis["type"],
        "reasons":         analysis["reasons"],
        "questions":       analysis["questions"],
        "urgency":         analysis["urgency"],
    })


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("transcript", None)
    log.info("Session transcript reset.")
    return jsonify({"status": "ok"})


@app.route("/transcript", methods=["GET"])
def get_transcript():
    return jsonify({
        "transcript": session.get("transcript", ""),
        "length":     len(session.get("transcript", "")),
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
