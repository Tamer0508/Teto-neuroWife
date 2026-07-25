import asyncio
import json
from websockets.asyncio.client import connect

from voice import Voice

URI = "ws://localhost:8765"


async def main():
    voice = Voice()

    while True:
        try:
            async with connect(URI) as websocket:
                print("[tts] подключился к хабу")

                async for message in websocket:
                    data = json.loads(message)
                    if data.get("type") != "teto_response":
                        continue

                    text = data["data"]["text"]
                    emotion = data["data"].get("emotion", "neutral")

                    print('Начинаем говорить')
                    await websocket.send(json.dumps(
                        {"type": "speech_started", "sender": "tts", "data": {}}))
            
                    await asyncio.to_thread(voice.speak, text, emotion)

                    print('Закончили говорить')
                    await websocket.send(json.dumps(
                        {"type": "speech_finished", "sender": "tts", "data": {}}))    # вся прежняя логика — сюда
        except Exception as e:
            print(f"[tts] соединение потеряно: {e}")

        print("[tts] переподключение через 3 с...")
        await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())