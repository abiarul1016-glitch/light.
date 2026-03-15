from openai import OpenAI

client = OpenAI()

def transcribe_audio(audio_file):

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    return transcription.text