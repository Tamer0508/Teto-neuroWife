import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from websockets.asyncio.client import connect

from vts import VTS
from hub_log import send_log

URI = "ws://localhost:8765"


async def main():
    vts = VTS()
    await vts.connect()

    async with connect(URI) as websocket:
        await send_log(websocket, "avatar", "Подключился к хабу")

        async for message in websocket:
            data = json.loads(message)
            if data.get("type") == "teto_response":
                emotion = data["data"].get("emotion", "neutral")
                await send_log(websocket, "avatar", f"Эмоция: {emotion}")
                await vts.set_emotion(emotion)


if __name__ == "__main__":
    asyncio.run(main())