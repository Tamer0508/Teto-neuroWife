import os
import time
import json
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv

from personality import TETO_SYSTEM_PROMPT
from memory import Memory

MODEL = "gemini-3.1-flash-lite"
EMOTIONS = ["joy", "neutral", "surprise", "sad", "embarrassed", "pout"]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "emotion": {"type": "string", "enum": EMOTIONS},
    },
    "required": ["text", "emotion"],
}


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
                    print(f"  [429] {e}")  
                    wait = min(2 ** attempt, 30)
                    print(f"  [лимит запросов, повтор через {wait} с...]")
                    time.sleep(wait)
                else:
                    raise
        return None                              # не удалось за max_retries попыток

    def respond(self, user_message: str) -> str:
        """Один ход диалога: вспомнить -> подумать -> запомнить -> вернуть текст."""
        t0 = time.perf_counter()
        memories = self.memory.recall(user_message)
        t1 = time.perf_counter()
        system_instruction = TETO_SYSTEM_PROMPT
        if memories:
            recalled = "\n".join(f"- {m}" for m in memories)
            system_instruction += (
                "\n\nЧто ты помнишь о собеседнике из прошлых разговоров "
                f"(используй это естественно, не зачитывай дословно):\n{recalled}"
            )
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        )
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        response = self._generate_with_retry(self.history, config)
        print(f"  [токены] {response.usage_metadata}")
        t2 = time.perf_counter()
        if response is None:
            self.history.pop()
            return {"text": "Ой, серверы Gemini сейчас перегружены...", "emotion": "sad"}
        data = json.loads(response.text)
        answer = data["text"]
        emotion = data["emotion"]
        self.history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
        self.memory.remember(user_message, answer)
        t3 = time.perf_counter()
        print(f"  [тайминг] recall={t1-t0:.2f}s  llm={t2-t1:.2f}s  remember={t3-t2:.2f}s")
        return {"text": answer, "emotion": emotion}