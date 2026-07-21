import asyncio
import json
from websockets.asyncio.client import connect

from brain import Brain

URI = "ws://localhost:8765"


async def main():
    brain = Brain()
    print("[brain] мозг загружен")

    async with connect(URI) as websocket:
        print("[brain] подключился к хабу")

        async for message in websocket:
            data = json.loads(message)

            # Реагируем только на реплики пользователя
            if data.get("type") != "user_message":
                continue

            user_text = data["data"]["text"]
            print(f"[brain] запрос: {user_text}")

            # respond() синхронный и медленный -> уводим в поток,
            # чтобы не заморозить event loop и не оборвать соединение
            answer = await asyncio.to_thread(brain.respond, user_text)

            envelope = {
                "type": "teto_response",
                "sender": "brain",
                "data": {"text": answer},
            }
            await websocket.send(json.dumps(envelope))
            print(f"[brain] ответ отправлен")


if __name__ == "__main__":
    asyncio.run(main())