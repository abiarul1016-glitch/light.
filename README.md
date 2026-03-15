# light.

*real-time protection for real conversations.*

[![watch the demo](https://img.youtube.com/vi/mHhYcOZPNXo/maxresdefault.jpg)](https://www.youtube.com/watch?v=mHhYcOZPNXo)

---

![Python](https://img.shields.io/badge/Python-3.8+-007bff?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-007bff?style=for-the-badge&logo=flask&logoColor=white)

---

*light.* listens to phone calls as they happen — transcribing, analyzing, and advising — so that the person on the line always knows what's really going on. Whether you're a senior being pressured by a scammer, a customer service agent trying to turn a frustrated caller around, or a sales rep feeling out a hesitant prospect, light. puts the right words in your hands at exactly the right time.

No post-call summaries. No "we'll review the tape later." Just quiet, real-time intelligence — delivered the moment you need it.

---

## Why this exists

Phone calls are one of the last truly vulnerable moments in modern communication. There's no paper trail, no time to think, no ability to quickly verify what you're being told. Scammers know this. So do bad managers and aggressive quotas.

In Canada alone, phone fraud costs victims hundreds of millions of dollars every year — and those numbers only capture the cases that get reported. The real toll is quieter: the 70-year-old who spent three days thinking she owed the CRA $4,200. The customer service rep who didn't know how to de-escalate and lost the account anyway. The sales call that ended in awkward silence because nobody knew when to stop pushing.

*light.* was built to change that calculus. Not by replacing the human on the call, but by standing behind them — invisible, instantaneous, and genuinely useful.

---

## What it does

*light.* has three modes, each built around a different kind of call:

### Scam Protection
*light.* listens for the patterns that scammers rely on — urgency, authority impersonation, threats, requests for unusual payment. It scores the likelihood that a call is fraudulent in real time, explains exactly *why* it's suspicious, and hands the user precise questions they can ask to expose the caller or safely end the conversation.

*Designed for seniors, caregivers, and anyone who's ever felt pressured on a call.*

### Customer Service
For agents on the front line, *light.* monitors customer sentiment throughout the call and scores satisfaction as it rises or falls. It surfaces observations about tone, frustration, and unresolved issues — and suggests empathetic, clear responses to help the agent guide the conversation toward a resolution the customer actually feels good about.

*Because the difference between a loyal customer and a cancelled account is often a single sentence.*

### Sales Rep
*light.* reads the room. It tracks buying signals, hesitation cues, and annoyance in real time — giving reps a live read on whether the customer is warming up or checking out. The suggested responses are deliberately non-pushy: moves that keep the conversation alive without burning the relationship.

*The best sales call is one where the customer forgets they're being sold to.*

---

## How it works

```
Microphone → 4-second audio chunks
           → Whisper (speech-to-text)
           → Accumulated transcript
           → LLM analysis (persona-specific prompt)
           → Live dashboard update
```

Every four seconds, *light.* captures a fresh chunk of audio, transcribes it with OpenAI Whisper, appends it to the growing call transcript, and fires it at a large language model with a carefully engineered prompt tuned to the active persona. The result — a score, a call type, a set of reasons, and three suggested responses — arrives in the dashboard within seconds.

The whole thing runs locally. No call audio leaves your machine except to the transcription model. Sessions are isolated per browser tab. Nothing is stored after you reset.

---

## Getting started

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

```
flask
flask-session
openai
openai-whisper
```

**2. Set your API key**

```bash
export OPENAI_API_KEY=your_key_here
```

**3. Run**

```bash
python app.py
```

Then open **http://localhost:5000** in your browser.

> **Note:** Microphone access requires the page to be served from `localhost` or a secure HTTPS origin. Opening it via a local IP address (e.g. `192.168.x.x`) will cause the browser to block microphone access — use `localhost` during development.

---

## Project structure

```
light/
├── app.py                  # Flask backend — transcription, analysis, session management
├── requirements.txt        # Python dependencies
├── README.md               # You're reading it
└── templates/
    └── index.html          # Complete frontend — splash, themes, dashboard, waveform
```

---

## API endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend |
| `POST` | `/analyze-chunk` | Accepts `audio` (file) + `persona` (string), returns analysis |
| `POST` | `/reset` | Clears the session transcript |
| `GET` | `/transcript` | Returns the current transcript (useful for debugging) |

The `/analyze-chunk` endpoint accepts `multipart/form-data` with two fields:
- `audio` — a WebM audio blob from the browser's MediaRecorder API
- `persona` — one of `scam`, `service`, or `sales`

It returns:

```json
{
  "chunk": "...the transcribed text of this audio chunk...",
  "full_transcript": "...everything transcribed so far...",
  "probability": 87.3,
  "type": "CRA Impersonation Scam",
  "reasons": ["Caller claims to be from a government agency", "..."],
  "questions": ["What is your official employee ID?", "..."],
  "urgency": "high",
  "persona": "scam"
}
```

---

## Swapping the transcription model

*light.* ships with Whisper `base`, which is fast and runs entirely on CPU. If transcription accuracy matters more than speed in your deployment, you can swap it out in a single line:

```python
# In app.py
whisper_model = whisper.load_model("medium")   # more accurate, slower
whisper_model = whisper.load_model("large-v3") # most accurate, GPU recommended
```

Alternatively, the audio pipeline is intentionally modular — you can replace the Whisper call in `analyze_chunk()` with any streaming STT service (Deepgram, AssemblyAI, Azure Speech) by swapping roughly 10 lines of code.

---

## Roadmap

These aren't promises — they're directions worth exploring.

- **Twilio integration** — full real-time phone call interception via Media Streams, so *light.* works on actual incoming calls without any speaker-phone setup
- **Voice biometrics** — flag known scammer voice signatures across calls
- **Post-call report generation** — export a structured summary with key moments, score timeline, and recommended follow-up actions
- **SMS & email modes** — extend the same intelligence to text-based channels
- **Mobile companion app** — run *light.* passively in the background during calls on iOS and Android

---

## A note on privacy

*light.* processes audio locally via Whisper and sends only the *text transcript* to the language model for analysis. No raw audio is transmitted to any external service beyond the transcription step. Sessions are stored server-side and scoped to individual browser tabs — they do not persist across server restarts.

For production deployments handling sensitive calls, we recommend reviewing your jurisdiction's consent and recording laws before deploying.

---

## Built with

- **[Flask](https://flask.palletsprojects.com/)** — lightweight Python web framework
- **[OpenAI Whisper](https://github.com/openai/whisper)** — open-source speech recognition
- **[Flask-Session](https://flask-session.readthedocs.io/)** — server-side session management
- **[Figtree](https://fonts.google.com/specimen/Figtree)** — the typeface powering the UI
- **The MediaRecorder API** — browser-native audio capture, no plugins required

---


  *light. — because the right words, at the right moment, change everything.*


---

<p align="center">
  Built at GenAiGenesis &nbsp;·&nbsp; Made with 💡
</p>
