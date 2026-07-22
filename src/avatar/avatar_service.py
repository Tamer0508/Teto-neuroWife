import asyncio
import json
from websockets.asyncio.client import connect

from vts import VTS

URI = "ws://localhost:8765"


async def main():
    vts = VTS()
    await vts.connect()

    async with connect(URI) as websocket:
        print("[avatar] подключился к хабу")

        async for message in websocket:
            data = json.loads(message)
            if data.get("type") == "teto_response":
                emotion = data["data"].get("emotion", "neutral")
                print(f"[avatar] эмоция: {emotion}")
                await vts.set_emotion(emotion)


if __name__ == "__main__":
    asyncio.run(main())