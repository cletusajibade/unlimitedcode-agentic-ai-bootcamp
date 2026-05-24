from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI() # Note: OpenAI SDKs are configured to automatically read your API key from the system environment.

try:
    models = client.models.list()
    for model in models:
        print(model.id)
except Exception as e:
    print(f"Error fetching models: {e}")
    raise