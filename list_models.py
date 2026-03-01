import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key)

print("Listing models...")
for model in client.models.list():
    print(f"Name: {model.name}, Supported Actions: {model.supported_actions}")
