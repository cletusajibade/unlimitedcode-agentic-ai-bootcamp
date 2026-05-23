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


response = client.responses.create(
    model="gpt-5.5",
    input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)