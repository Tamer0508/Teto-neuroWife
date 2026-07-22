import asyncio
import json
from websockets.asyncio.client import connect

from voice import Voice

URI = "ws://localhost:8765"


async def main():
    voice = Voice()

    async with connect(URI) as websocket:
        print("[tts] подключился к хабу")
        async for message in websocket:
            data = json.loads(message)
            if data.get("type") != "teto_response":
                continue
        
            text = data["data"]["text"]

            await asyncio.to_thread(voice.speak, text)


if __name__ == "__main__":
    asyncio.run(main())