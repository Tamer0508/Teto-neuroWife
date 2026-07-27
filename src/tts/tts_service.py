import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from websockets.asyncio.client import connect

from voice import Voice
from hub_log import send_log

URI = "ws://localhost:8765"


async def main():
    voice = Voice()

    while True:
        try:
            async with connect(URI) as websocket:
                await send_log(websocket, "tts", "Подключился к хабу")

                async for message in websocket:
                    data = json.loads(message)
                    if data.get("type") != "teto_response":
                        continue

                    text = data["data"]["text"]
                    emotion = data["data"].get("emotion", "neutral")

                    await send_log(websocket, "tts", f"Синтез ({emotion}): {text[:40]}")
                    await websocket.send(json.dumps(
                        {"type": "speech_started", "sender": "tts", "data": {}}))

                    await asyncio.to_thread(voice.speak, text, emotion)

                    await send_log(websocket, "tts", "Аудио ушло в CABLE")
                    await websocket.send(json.dumps(
                        {"type": "speech_finished", "sender": "tts", "data": {}}))
        except Exception as e:
            await send_log(websocket, "tts", f"Соединение потеряно: {e}", level="warn")

        print("[tts] переподключение через 3 с...")
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())