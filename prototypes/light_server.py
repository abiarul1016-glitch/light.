from flask import Flask, request, jsonify, render_template
import whisper
import os
import json
from openai import OpenAI

# -----------------------------
# GPT OSS setup
# -----------------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "test"),
    base_url="https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
)

# -----------------------------
# Whisper model
# -----------------------------
whisper_model = whisper.load_model("base")

# -----------------------------
# Helper for GPT output
# -----------------------------
def extract_text(resp):
    choice = resp.choices[0]
    text = getattr(choice.message, "content", None)

    if text is None:
        text = getattr(choice.message, "reasoning", None)

    return text

# -----------------------------
# Scam analysis
# -----------------------------
def analyze_transcript(transcript):

    prompt = f"""
Analyze this phone call transcript.

Return JSON:
{{
"probability": number between 0 and 1,
"type": "scam type",
"questions": ["question1","question2","question3"]
}}

Transcript:
{transcript}
"""

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are an expert fraud detection assistant."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
    )

    text = extract_text(resp)

    try:
        result = json.loads(text)
    except:
        result = {
            "probability": 0.5,
            "type": "Unknown",
            "questions": [
                "Ask for employee ID",
                "Ask for office location",
                "Tell them you will call the official number",
            ],
        }

    return result


# -----------------------------
# Flask server
# -----------------------------

app = Flask(__name__)

from flask import send_file

@app.route("/")
def index():
    return render_template("index.html")

full_transcript = ""

@app.route("/analyze-chunk", methods=["POST"])
def analyze_chunk():

    global full_transcript

    audio = request.files["audio"]
    path = "chunk.wav"
    audio.save(path)

    result = whisper_model.transcribe(path)
    chunk_text = result["text"]

    full_transcript += " " + chunk_text

    analysis = analyze_transcript(full_transcript)

    probability = float(analysis["probability"]) * 100

    return jsonify({
        "chunk": chunk_text,
        "full_transcript": full_transcript,
        "probability": probability,
        "type": analysis["type"],
        "questions": analysis["questions"]
    })


if __name__ == "__main__":
    app.run(debug=True)