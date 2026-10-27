
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(".env", override=True)

key = os.getenv("GEMINI_API_KEY")
if not key:
    raise SystemExit("GEMINI_API_KEY is missing from .env")

client = genai.Client(api_key=key)

try:
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Reply with just OK"
    )
    print("SUCCESS:", response.text)
except Exception as e:
    print("FAILED:", type(e).__name__)
    print("DETAILS:", str(e)[:1000])
