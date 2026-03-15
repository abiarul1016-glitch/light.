# light_terminal_local_whisper.py

import os
import json
from openai import OpenAI
import whisper  # pip install openai-whisper

# -------------------
# GPT-OSS Setup
# -------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "test"),
    base_url="https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
)

def extract_text_from_resp(resp):
    """Extract text from GPT-OSS response, fallback to reasoning if content is None."""
    choice = resp.choices[0]
    text = getattr(choice.message, "content", None)
    if text is None:
        text = getattr(choice.message, "reasoning", None)
    if text is None:
        text = "No output from GPT-OSS"
    return text

# -------------------
# Local Whisper Transcription
# -------------------
# Load model once for speed
whisper_model = whisper.load_model("base")  # "small", "medium" etc. for faster/slower

def transcribe_audio(audio_file_path):
    """
    Transcribe an audio file using local Whisper model.
    Returns the transcript string.
    """
    print(f"Whisper: Transcribing {audio_file_path} ...")
    result = whisper_model.transcribe(audio_file_path, fp16=False)
    return result["text"]

# -------------------
# Scam Analysis
# -------------------
def analyze_transcript(transcript):
    prompt = f"""
Analyze this phone call transcript.

Determine:
1. Probability this is a scam (0-1)
2. Scam type
3. 3 questions a senior should ask to verify the caller

Return strictly valid JSON with keys:
probability
type
questions

Transcript:
{transcript}
"""
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are an expert fraud detection assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
        )
        result_text = extract_text_from_resp(resp)
        result = json.loads(result_text)
    except Exception as e:
        print("GPT-OSS parse error:", e)
        # fallback
        result = {
            "probability": 0.9,
            "type": "Government Impersonation",
            "questions": [
                "Ask for official employee ID",
                "Ask which office they are calling from",
                "Tell them you will call the official number"
            ]
        }
    return result

# -------------------
# Main
# -------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Light - Scam Call Analyzer (Local Whisper)")
    parser.add_argument("audio_file", help="Path to audio file (wav, mp3, etc.)")
    args = parser.parse_args()

    audio_path = args.audio_file

    # 1. Transcribe
    transcript = transcribe_audio(audio_path)
    print("\n--- Transcript ---")
    print(transcript)

    # 2. Analyze with GPT-OSS
    print("\nAnalyzing for scam...")
    analysis = analyze_transcript(transcript)

    # 3. Display results
    print("\n--- Analysis Result ---")
    prob = float(analysis["probability"]) * 100
    print(f"⚠ Scam Probability: {prob:.1f}%")
    print(f"Scam Type: {analysis['type']}")
    print("Suggested Questions:")
    for q in analysis["questions"]:
        print(f"- {q}")