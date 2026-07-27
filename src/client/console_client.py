import asyncio
import json
from websockets.asyncio.client import connect

URI = "ws://localhost:8765"


async def receiver(websocket):
    """Корутина №1: бесконечно слушает хаб и печатает ответы Тето."""
    async for message in websocket:
        data = json.loads(message)
        if data["type"] == "teto_response":
            text = data["data"]["text"]
            emotion = data["data"].get("emotion", "neutral")
            print(f"\nТето [{emotion}]: {text}\n")


async def sender(websocket):
    """Корутина №2: бесконечно читает твой ввод и шлёт его в хаб."""
    while True:
        text = await asyncio.to_thread(input, "Ты: ")

        text = text.strip()
        if not text:
            continue

        # команды переключения личности: /kind, /mean
        if text in ("/kind", "/mean"):
            mode = text[1:]   # убираем "/" -> "kind" / "mean"
            command = {"type": "set_personality", "sender": "console", "data": {"mode": mode}}
            await websocket.send(json.dumps(command))
            print(f"[console] переключаю личность: {mode}")
            continue          # это команда, не реплика — дальше не шлём

        envelope = {"type": "user_message", "sender": "console", "data": {"text": text}}
        await websocket.send(json.dumps(envelope))


async def main():
    async with connect(URI) as websocket:
        print("[console] подключился к хабу")
        print("[console] команды: /kind — добрая, /mean — дерзкая\n")
        await asyncio.gather(receiver(websocket), sender(websocket))


if __name__ == "__main__":
    asyncio.run(main())