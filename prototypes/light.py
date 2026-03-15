import os

from dotenv import load_dotenv
from openai import OpenAI

# 1. Load the file ONLY if it exists (for your local Mac/PC)
if os.path.exists('secrets.env'):
    load_dotenv('secrets.env')

# 2. Pull the variables (works for both local and GitHub)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 3. CRITICAL: Add a tiny debug check (don't worry, it won't print your password)
if not OPENAI_API_KEY:
    print("❌ ERROR: Credentials not found in environment!")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "test"),  # "test" works for hackathon server
    base_url="https://vjioo4r1vyvcozuj.us-east-2.aws.endpoints.huggingface.cloud/v1",
)

def main():

    # Test OpenAI API
    resp = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hey there!"},],
        max_tokens=50,
    )

    output_text = extract_text_from_resp(resp)
    print("GPT output:", output_text)

def extract_text_from_resp(resp):
    choice = resp.choices[0]

    # First try the usual field
    text = getattr(choice.message, "content", None)

    # Fallback to 'reasoning' field used by GPT-OSS hackathon server
    if text is None:
        text = getattr(choice.message, "reasoning", None)

    # Ultimate fallback
    if text is None:
        text = "No output from GPT-OSS"

    return text

    # Get audio file from user
    #   in future this will actually be a live transcription of user call


    # Process the transcription

    # Feed the live transcription in chunks to the LLM

    # Use the LLM response to decide the scam score of the call and what action to take next


def transcribe_audio(audio_file):

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )

    return transcription.text


def analyze_transcript(transcript):

    prompt = f"""
    Analyze the following phone call transcript.

    Determine:
    1. Probability this is a scam (0-1)
    2. Scam type
    3. 3 questions the user should ask to verify the caller

    Transcript:
    {transcript}

    Return JSON with:
    probability
    type
    questions
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert fraud detection assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    result = response.choices[0].message.content

    return eval(result)



if __name__ == '__main__':
    main()