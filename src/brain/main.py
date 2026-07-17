import os
import time
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv

from personality import TETO_SYSTEM_PROMPT
from memory import Memory

DEBUG = True

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("Не найден GEMINI_API_KEY — проверь файл .env")

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3-flash-preview"

memory = Memory()
history: list[types.Content] = []


def generate_with_retry(contents, config, max_retries=5):
    """Запрос к модели с повторами при временных ошибках сервера."""
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL, contents=contents, config=config
            )
        except errors.ServerError as e:          # 5xx, включая 503 "high demand"
            wait = min(2 ** attempt, 30)
            print(f"  [сервер занят ({e.code}), повтор через {wait} с...]")
            time.sleep(wait)
        except errors.ClientError as e:
            if e.code == 429:                    # превышен лимит запросов
                wait = min(2 ** attempt, 30)
                print(f"  [лимит запросов, повтор через {wait} с...]")
                time.sleep(wait)
            else:
                raise                            # прочие 4xx (битый запрос) — не повторяем
    return None                                  # не удалось за max_retries попыток


print("Тето проснулась! Пиши ей (или 'выход' чтобы закончить).\n")

while True:
    user_message = input("Ты: ").strip()

    if user_message.lower() in ("выход", "exit", "quit"):
        print("Тето: Пока-пока!")
        break

    if not user_message:
        continue

    # 1. Вспоминаем релевантное
    memories = memory.recall(user_message)
    if DEBUG and memories:
        print(f"  [вспомнила {len(memories)} фрагмент(ов)]")

    # 2. Системная инструкция: характер + воспоминания
    system_instruction = TETO_SYSTEM_PROMPT
    if memories:
        recalled = "\n".join(f"- {m}" for m in memories)
        system_instruction += (
            "\n\nЧто ты помнишь о собеседнике из прошлых разговоров "
            f"(используй это естественно, не зачитывай дословно):\n{recalled}"
        )

    config = types.GenerateContentConfig(system_instruction=system_instruction)

    # 3. Реплика пользователя -> в историю
    history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    # 4. Запрос с повторами
    response = generate_with_retry(history, config)
    if response is None:
        print("Тето: Ой, серверы Gemini сейчас перегружены. Попробуй ещё раз чуть позже.\n")
        history.pop()   # убираем неотвеченную реплику, чтобы история не поехала
        continue

    answer = response.text

    # 5. Ответ Тето -> в историю
    history.append(types.Content(role="model", parts=[types.Part(text=answer)]))

    # 6. Сохраняем обмен в долговременную память
    memory.remember(user_message, answer)

    print(f"Тето: {answer}\n")