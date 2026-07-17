import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

from personality import TETO_SYSTEM_PROMPT

# Загружаем переменные из .env в окружение процесса
load_dotenv()

# Достаём ключ. Если его нет — сразу понятная ошибка, а не непонятный сбой позже.
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("Не найден GEMINI_API_KEY — проверь файл .env")

# Клиент — точка входа в Gemini API
client = genai.Client(api_key=API_KEY)

MODEL = "gemini-3-flash-preview"

# Создаём чат-сессию. Она сама хранит историю диалога внутри,
# поэтому Тето помнит контекст в рамках одного запуска.
chat = client.chats.create(
    model=MODEL,
    config=types.GenerateContentConfig(
        system_instruction=TETO_SYSTEM_PROMPT,
    ),
)

print("Тето проснулась! Пиши ей (или 'выход' чтобы закончить).\n")

while True:
    user_message = input("Ты: ").strip()

    if user_message.lower() in ("выход", "exit", "quit"):
        print("Тето: Пока-пока!")
        break

    if not user_message:
        continue

    response = chat.send_message(user_message)
    print(f"Тето: {response.text}\n")