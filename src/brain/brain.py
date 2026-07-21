import os
import time
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv

from personality import TETO_SYSTEM_PROMPT
from memory import Memory

MODEL = "gemini-3-flash-preview"


class Brain:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise SystemExit("Не найден GEMINI_API_KEY — проверь файл .env")

        self.client = genai.Client(api_key=api_key)
        self.memory = Memory()
        self.history: list[types.Content] = []

    def _generate_with_retry(self, contents, config, max_retries=5):
        """Запрос к модели с повторами при временных ошибках сервера."""
        for attempt in range(max_retries):
            try:
                return self.client.models.generate_content(
                    model=MODEL, contents=contents, config=config
                )
            except errors.ServerError as e:
                wait = min(2 ** attempt, 30)
                print(f"  [сервер занят ({e.code}), повтор через {wait} с...]")
                time.sleep(wait)
            except errors.ClientError as e:
                if e.code == 429:
                    wait = min(2 ** attempt, 30)
                    print(f"  [лимит запросов, повтор через {wait} с...]")
                    time.sleep(wait)
                else:
                    raise
        return None                              # не удалось за max_retries попыток

    def respond(self, user_message: str) -> str:
        """Один ход диалога: вспомнить -> подумать -> запомнить -> вернуть текст."""
        memories = self.memory.recall(user_message)
        system_instruction = TETO_SYSTEM_PROMPT
        if memories:
            recalled = "\n".join(f"- {m}" for m in memories)
            system_instruction += (
                "\n\nЧто ты помнишь о собеседнике из прошлых разговоров "
                f"(используй это естественно, не зачитывай дословно):\n{recalled}"
            )
        config = types.GenerateContentConfig(system_instruction=system_instruction)
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        response = self._generate_with_retry(self.history, config)
        if response is None:
            self.history.pop()
            return "Ой, серверы Gemini сейчас перегружены. Попробуй ещё раз чуть позже."

        answer = response.text
        self.history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
        self.memory.remember(user_message, answer)
        return answer