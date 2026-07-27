import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from websockets.asyncio.client import connect

from brain import Brain
from vision import capture_screen
from hub_log import send_log

URI = "ws://localhost:8765"


async def main():
    brain = Brain()
    print("[brain] мозг загружен")

    async with connect(URI) as websocket:
        await send_log(websocket, "brain", "Подключился к хабу")

        async for message in websocket:
            data = json.loads(message)
            mtype = data.get("type")

            # переключение личности — ловим ДО фильтра на user_message
            if mtype == "set_personality":
                mode = data["data"]["mode"]
                if brain.set_personality(mode):
                    await send_log(websocket, "brain", f"Личность переключена: {mode}")
                else:
                    await send_log(websocket, "brain", f"Нет такой личности: {mode}", level="warn")
                continue

            if mtype != "user_message":
                continue

            user_text = data["data"]["text"]
            await send_log(websocket, "brain", f"Реплика: {user_text[:60]}")

            await send_log(websocket, "brain", "Запрос к Gemini...")
            result = await asyncio.to_thread(brain.respond, user_text)

            if result.get("needs_screen"):
                await send_log(websocket, "brain", "Нужен экран — делаю скриншот")
                filler = {
                    "type": "teto_response",
                    "sender": "brain",
                    "data": {"text": result["text"], "emotion": result["emotion"]},
                }
                await websocket.send(json.dumps(filler))

                image = await asyncio.to_thread(capture_screen)
                result = await asyncio.to_thread(brain.respond, user_text, image)

            await send_log(websocket, "memory", f"Recall: {result.get('recalled', 0)} фрагм.")

            if result.get("error"):
                await send_log(websocket, "brain", "Gemini не ответил, ушла заглушка", level="error")
            else:
                await send_log(websocket, "brain", f"Ответ готов: emotion={result['emotion']}")

            envelope = {
                "type": "teto_response",
                "sender": "brain",
                "data": {"text": result["text"], "emotion": result["emotion"]},
            }
            await websocket.send(json.dumps(envelope))

            # факты: обновляем память после ответа
            if not result.get("needs_screen") and not result.get("error"):
                changes = await asyncio.to_thread(brain.remember_facts, user_text, result["text"])
                if changes:
                    await send_log(websocket, "memory", f"Память: {', '.join(changes)}")
                else:
                    await send_log(websocket, "memory", "Память без изменений")


if __name__ == "__main__":
    asyncio.run(main())