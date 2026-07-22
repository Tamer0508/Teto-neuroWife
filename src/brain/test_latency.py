import os, time
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

t0 = time.perf_counter()
r = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Скажи одно слово: привет",
)
print(f"{time.perf_counter() - t0:.2f}s")
print(r.text)
print(r.usage_metadata)