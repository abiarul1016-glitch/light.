import ssl
import whisper

ssl._create_default_https_context = ssl._create_unverified_context

model = whisper.load_model("turbo")
result = model.transcribe("test.mp3", fp16=False)
print(result["text"])