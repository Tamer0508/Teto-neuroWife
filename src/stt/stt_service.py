import asyncio
import json
from websockets.asyncio.client import connect

from listener import Listener

URI = "ws://localhost:8765"


class State:
    """Общее состояние между корутинами."""
    def __init__(self):
        self.teto_speaking = False


async def receiver(websocket, state):
    """Слушает хаб и обновляет флаг: говорит ли сейчас Тето."""
    async for message in websocket:
        data = json.loads(message)
        msg_type = data.get("type")
        if msg_type == "speech_started":
            state.teto_speaking = True
        if msg_type == "speech_finished":
            state.teto_speaking = False


async def sender(websocket, state, listener):
    """Слушает микрофон и шлёт распознанное в хаб."""
    while True:
        if state.teto_speaking: 
            await asyncio.sleep(0.1)
            continue

        audio = await asyncio.to_thread(listener.listen)
        if audio is None:
            continue

        if state.teto_speaking:
            continue

        text = await asyncio.to_thread(listener.transcribe, audio)
        if not text.strip():
            continue

        envelope = {"type": "user_message", "sender": "stt", "data": {"text": text}}
        print(f"[stt] распознано: {text}")
        await websocket.send(json.dumps(envelope))


async def main():
    listener = Listener()
    state = State()

    async with connect(URI) as websocket:
        print("[stt] подключился к хабу")
        await asyncio.gather(receiver(websocket, state), sender(websocket, state, listener))


if __name__ == "__main__":
    asyncio.run(main())