import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

print("Listing available models...")
try:
    for m in client.models.list():
        # Just print the name and display_name if available
        print(f"- {m.name} ({getattr(m, 'display_name', 'No display name')})")
except Exception as e:
    print(f"Error listing models: {e}")
