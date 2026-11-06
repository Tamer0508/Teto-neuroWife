import os
import time
import json
from google import genai
from google.genai import types, errors
from dotenv import load_dotenv
from google.genai import types

from personality import PERSONALITIES, DEFAULT_MODE
from memory import Memory

MODEL = "gemini-3.1-flash-lite"
EMOTIONS = ["joy", "neutral", "surprise", "sad", "embarrassed", "pout"]

MAX_HISTORY_PAIRS = 10   # сколько последних обменов держим в контексте

# --- кто говорит: ярлыки для промпта ---
LABEL_OWNER = "Хозяин"
LABEL_DISCORD = "Кто-то в Discord"

# пояснение модели, как читать ярлыки (добавляется в system каждый ход)
SPEAKER_NOTE = (
    "\n\nВ диалоге реплики помечены, кто говорит:\n"
    "- «Хозяин:» — твой владелец, тот, с кем ты общаешься постоянно и кого помнишь.\n"
    "- «Кто-то в Discord:» — другой человек в голосовом чате. Это НЕ хозяин, "
    "по именам ты их не знаешь, но можешь им отвечать. Не путай их с хозяином "
    "и не приписывай им то, что помнишь о хозяине."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "emotion": {"type": "string", "enum": EMOTIONS},
        "needs_screen": {"type": "boolean"},
    },
    "required": ["text", "emotion", "needs_screen"],
}

# --- извлечение и обновление фактов в памяти ---
FACT_EXTRACTION_PROMPT = """Ты — модуль долговременной памяти Тето. На входе: список уже
известных фактов о СОБЕСЕДНИКЕ (каждый со своим id) и новый обмен репликами.

ВАЖНО, кто есть кто:
- «Собеседник:» — это человек, о котором ты ведёшь память. Факты собираешь ТОЛЬКО про него.
- «Тето ответила:» — это сама Тето (виртуальная девушка). Факты о НЕЙ в память НЕ добавляй
  никогда. Если Тето говорит о себе («мне 31», «люблю багет», «я химера») — это её характер,
  а не факт о собеседнике. Игнорируй такое полностью.
- Факт засчитывается, только если он про собеседника и следует из ЕГО слов (реплики
  «Собеседник:»). То, что сказала Тето, — не источник фактов о собеседнике.

Твоя задача — решить, как обновить память, и вернуть список операций:
- {"action": "add", "text": "новый факт"} — новый устойчивый факт о собеседнике, которого
  ещё нет в памяти.
- {"action": "replace", "id": "id_старого", "text": "новый факт"} — новый факт уточняет или
  исправляет уже известный (изменилось имя, предпочтение, обстоятельство). id бери из списка.

Правила:
- Сохраняй только устойчивые факты о собеседнике: имя, возраст, род занятий, предпочтения,
  важные обстоятельства, планы, отношения. Игнорируй болтовню, приветствия, эмоции.
- НЕ добавляй факт, если он уже есть в памяти (даже другими словами) — это дубль, пропусти.
- Если факт противоречит известному — replace, а не add.
- Формулируй кратко, от третьего лица: "Зовут Лакейт", "Любит багеты".
- Если обновлять нечего — верни пустой список.

Верни строго JSON: {"operations": [ ... ]}. Пусто — {"operations": []}."""

FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["add", "replace"]},
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["action", "text"],
            },
        },
    },
    "required": ["operations"],
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
        self.mode = DEFAULT_MODE

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

    def set_personality(self, mode: str) -> bool:
        """Переключить личность. True — режим применён, False — нет такого режима."""
        if mode not in PERSONALITIES:
            return False
        self.mode = mode
        return True

    def respond(self, user_message: str, image: bytes | None = None,
                source: str | None = None) -> dict:
        """Один ход диалога. image — если Тето смотрит на экран.
        source: None/"mic" — говорит хозяин (микрофон); "desktop" — реплика из Discord.
        ВНИМАНИЕ: память тут больше не трогается — этим занимается brain_service
        после отправки ответа (чтобы не тормозить речь Тето)."""
        t0 = time.perf_counter()
        memories = self.memory.recall(user_message)
        t1 = time.perf_counter()

        system_instruction = PERSONALITIES[self.mode]
        if memories:
            recalled = "\n".join(f"- {m}" for m in memories)
            system_instruction += (
                "\n\nЧто ты помнишь о хозяине из прошлых разговоров "
                f"(используй это естественно, не зачитывай дословно):\n{recalled}"
            )
        system_instruction += SPEAKER_NOTE

        # помечаем реплику ярлыком говорящего
        label = LABEL_DISCORD if source == "desktop" else LABEL_OWNER
        tagged = f"{label}: {user_message}"

        parts = [types.Part(text=tagged)]
        if image is not None:
            parts.append(types.Part.from_bytes(data=image, mime_type="image/jpeg"))

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
        )

        contents = self.history + [types.Content(role="user", parts=parts)]
        response = self._generate_with_retry(contents, config)
        t2 = time.perf_counter()

        if response is None:
            return {"text": "Ой, серверы Gemini сейчас перегружены...",
                    "emotion": "sad", "needs_screen": False, "error": True,
                    "recalled": len(memories)}

        print(f"  [токены] {response.usage_metadata}")
        data = json.loads(response.text)
        answer = data["text"]
        emotion = data["emotion"]
        needs_screen = data["needs_screen"]

        # В историю кладём ТОЛЬКО финальный ответ (не запрос скриншота),
        # реплику юзера — с ярлыком, но без картинки, чтобы не раздувать контекст.
        if not needs_screen:
            self.history.append(types.Content(role="user", parts=[types.Part(text=tagged)]))
            self.history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
            # держим последние N пар; режем КРАТНО 2, чтобы не осталось
            # висячего model без своего user (Gemini требует чередования ролей)
            self.history = self.history[-MAX_HISTORY_PAIRS * 2:]

        print(f"  [тайминг] recall={t1-t0:.2f}s  llm={t2-t1:.2f}s")
        return {"text": answer, "emotion": emotion, "needs_screen": needs_screen,
                "recalled": len(memories)}

    def remember_facts(self, user_message: str, teto_message: str,
                       source: str | None = None) -> list[str]:
        """Обновить память по обмену: добавить новые факты, заменить устаревшие.
        Зовётся из brain_service ПОСЛЕ отправки ответа. Возвращает описания изменений.
        Для source="desktop" (реплика из Discord) память НЕ трогаем: голоса собеседников
        мы не различаем, и их факты не должны смешиваться с фактами о хозяине."""
        if source == "desktop":
            return []

        known = self.memory.all_facts()
        operations = self._extract_facts(user_message, teto_message, known)

        changes = []
        for op in operations:
            action = op.get("action")
            text = op.get("text", "").strip()
            if not text:
                continue

            if action == "add":
                self.memory.remember_fact(text)
                changes.append(f"+{text}")
            elif action == "replace":
                old_id = op.get("id")
                if old_id:
                    self.memory.delete_fact(old_id)   # убираем устаревший
                self.memory.remember_fact(text)       # кладём уточнённый
                changes.append(f"~{text}")
        return changes

    def _extract_facts(self, user_message: str, teto_message: str, known: list[dict]) -> list[dict]:
        """Запрос к модели: какие операции над памятью нужны по этому обмену."""
        # список известных фактов с id — чтобы модель могла ссылаться на них для replace
        if known:
            known_block = "\n".join(f'[{f["id"]}] {f["text"]}' for f in known)
        else:
            known_block = "(память пуста)"

        prompt = (
            f"Известные факты о собеседнике:\n{known_block}\n\n"
            f"Новый обмен:\nСобеседник: {user_message}\nТето ответила: {teto_message}"
        )
        config = types.GenerateContentConfig(
            system_instruction=FACT_EXTRACTION_PROMPT,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL"),
            response_mime_type="application/json",
            response_schema=FACT_SCHEMA,
        )
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        response = self._generate_with_retry(contents, config)
        if response is None:
            return []
        try:
            data = json.loads(response.text)
            return data.get("operations", [])
        except (json.JSONDecodeError, KeyError):
            return []