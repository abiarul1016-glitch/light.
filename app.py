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

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "test"),
    base_url="https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
)

log.info("Loading Whisper model…")
whisper_model = whisper.load_model("base")
log.info("Whisper ready.")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", uuid.uuid4().hex)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = tempfile.mkdtemp(prefix="light_sessions_")
app.config["SESSION_PERMANENT"] = False
Session(app)

# ─────────────────────────────────────────
# Persona system prompts
# ─────────────────────────────────────────

PROMPTS = {
    "scam": """You are an expert fraud detection assistant specialising in Canadian phone scams.
Analyze the phone call transcript and return ONLY a valid JSON object — no markdown, no extra text.

Common Canadian scam patterns: CRA impersonation, Service Canada fraud, TD/RBC/Scotiabank impersonation,
RCMP impersonation, arrest threats, deportation threats, gift card payments, SIN number requests, prize scams.

Return exactly:
{
  "probability": <float 0-1, scam likelihood>,
  "type": "<concise scam category or 'Legitimate call'>",
  "reasons": ["<why flagged 1>", "<why flagged 2>"],
  "questions": ["<verification question 1>", "<verification question 2>", "<verification question 3>"],
  "urgency": "<low|medium|high>"
}""",

    "service": """You are an expert customer service quality analyst. Analyze this customer service call transcript.
Score customer satisfaction from 0 (extremely dissatisfied) to 1 (very satisfied).
Return ONLY a valid JSON object — no markdown, no extra text.

Return exactly:
{
  "probability": <float 0-1, satisfaction score — higher is better>,
  "type": "<call category: billing_issue|technical_problem|complaint|general_inquiry|praise|refund_request>",
  "reasons": ["<key observation about customer sentiment>", "<another observation about call quality>"],
  "questions": [
    "<open-ended question to better understand the customer's problem>",
    "<empathetic phrase or action to comfort the customer>",
    "<a clear, jargon-free instruction or next step to offer>"
  ],
  "urgency": "<low|medium|high based on customer frustration level>"
}""",

    "sales": """You are an expert sales coach analyzing a live sales call.
Score the customer's likelihood to purchase from 0 (not interested) to 1 (ready to buy).
Return ONLY a valid JSON object — no markdown, no extra text.

Return exactly:
{
  "probability": <float 0-1, purchase likelihood — higher is better>,
  "type": "<customer state: very_interested|mildly_interested|hesitant|neutral|annoyed|not_interested|ready_to_buy>",
  "reasons": ["<buying signal or objection observed>", "<another signal>"],
  "questions": [
    "<non-pushy way to gauge or deepen interest>",
    "<gentle objection-handling approach that doesn't irritate>",
    "<subtle next step or soft close suggestion>"
  ],
  "urgency": "<low|medium|high based on customer's buying urgency>"
}"""
}

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _extract_content(resp) -> str:
    msg = resp.choices[0].message
    return (getattr(msg, "content", None) or getattr(msg, "reasoning", None) or "").strip()


def _parse_json(raw: str) -> dict:
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
    log.warning("Could not parse JSON: %r", raw[:300])
    return {}


def _safe_defaults(persona: str) -> dict:
    defaults = {
        "scam": {
            "probability": 0.5, "type": "Unknown",
            "reasons": ["Could not analyse transcript."],
            "questions": ["Can you provide your official employee ID?",
                          "What is your department's direct callback number?",
                          "I'll verify by calling the official number from the website."],
            "urgency": "medium",
        },
        "service": {
            "probability": 0.5, "type": "general_inquiry",
            "reasons": ["Not enough context to evaluate call quality."],
            "questions": ["Could you describe the issue in a bit more detail?",
                          "I completely understand how frustrating that must be.",
                          "Here's what I'll do to resolve this for you right now."],
            "urgency": "low",
        },
        "sales": {
            "probability": 0.3, "type": "neutral",
            "reasons": ["Insufficient context to gauge interest level."],
            "questions": ["What's the biggest challenge you're trying to solve today?",
                          "I hear you — let me show you exactly how this addresses that concern.",
                          "Would it make sense to schedule a quick follow-up this week?"],
            "urgency": "low",
        },
    }
    return defaults.get(persona, defaults["scam"])


def _normalise(raw: dict) -> dict:
    try:
        prob = max(0.0, min(1.0, float(raw.get("probability", 0.5))))
    except (TypeError, ValueError):
        prob = 0.5
    return {
        "probability": prob,
        "type":        str(raw.get("type", "Unknown")),
        "reasons":     list(raw.get("reasons", [])),
        "questions":   list(raw.get("questions", [])),
        "urgency":     str(raw.get("urgency", "low")),
    }


def analyze_transcript(transcript: str, persona: str) -> dict:
    if not transcript.strip():
        return _safe_defaults(persona)
    system_prompt = PROMPTS.get(persona, PROMPTS["scam"])
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": f"Analyze this transcript:\n\n{transcript}"},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        raw = _extract_content(resp)
        result = _parse_json(raw)
    except OpenAIError as exc:
        log.error("LLM request failed: %s", exc)
        return _safe_defaults(persona)
    return _normalise(result) if result else _safe_defaults(persona)


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

    persona = request.form.get("persona", "scam")
    if persona not in PROMPTS:
        persona = "scam"

    suffix = os.path.splitext(audio_file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        audio_file.save(tmp_path)

    try:
        result = whisper_model.transcribe(tmp_path, language="en")
        chunk_text = result["text"].strip()
        log.info("Transcribed [%s] (%d chars): %s…", persona, len(chunk_text), chunk_text[:80])
    except Exception as exc:
        log.error("Whisper failed: %s", exc)
        return jsonify({"error": "Transcription failed"}), 500
    finally:
        os.unlink(tmp_path)

    session.setdefault("transcript", "")
    session["transcript"] = (session["transcript"] + " " + chunk_text).strip()
    session["persona"] = persona
    session.modified = True

    analysis = analyze_transcript(session["transcript"], persona)

    return jsonify({
        "chunk":           chunk_text,
        "full_transcript": session["transcript"],
        "probability":     round(analysis["probability"] * 100, 1),
        "type":            analysis["type"],
        "reasons":         analysis["reasons"],
        "questions":       analysis["questions"],
        "urgency":         analysis["urgency"],
        "persona":         persona,
    })


@app.route("/reset", methods=["POST"])
def reset():
    session.pop("transcript", None)
    session.pop("persona", None)
    return jsonify({"status": "ok"})


@app.route("/transcript", methods=["GET"])
def get_transcript():
    return jsonify({"transcript": session.get("transcript", ""), "persona": session.get("persona", "scam")})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)