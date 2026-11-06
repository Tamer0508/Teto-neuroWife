import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import time
from websockets.asyncio.client import connect

from loopback_listener import LoopbackListener
from hub_log import send_log

URI = "ws://localhost:8765"
COOLDOWN = 1.0   # сек паузы после речи Тето, прежде чем уши снова слушают (эхо/хвост отзвенит)


class State:
    def __init__(self):
        self.teto_speaking = False
        self.last_speech_end = 0.0

    def muted(self) -> bool:
        """Уши должны молчать: Тето говорит ИЛИ ещё не отзвенел хвост после речи."""
        return self.teto_speaking or (time.time() - self.last_speech_end) < COOLDOWN


async def receiver(websocket, state):
    """Пока Тето говорит — уши молчат (иначе она слышит себя)."""
    async for message in websocket:
        data = json.loads(message)
        msg_type = data.get("type")

        if msg_type == "log":
            continue
        if msg_type == "speech_started":
            state.teto_speaking = True
        if msg_type == "speech_finished":
            state.teto_speaking = False
            state.last_speech_end = time.time()


async def sender(websocket, state, listener):
    """Слушает Discord и шлёт распознанное, но молчит, пока говорит Тето."""
    while True:
        if state.muted():
            await asyncio.sleep(0.1)
            continue

        # обрываем захват, если Тето заговорит посреди фразы
        audio = await asyncio.to_thread(listener.listen, lambda: state.teto_speaking)
        if audio is None:
            continue

        # вдруг Тето заговорила прямо в конце захвата — не отправляем её же голос
        if state.muted():
            continue

        text = await asyncio.to_thread(listener.transcribe, audio)
        if not text.strip():
            continue

        envelope = {"type": "user_message", "sender": "ears",
                    "data": {"text": text, "source": "desktop"}}
        await send_log(websocket, "ears", f"Услышала (Discord): {text}")
        await websocket.send(json.dumps(envelope))


async def main():
    listener = LoopbackListener()
    state = State()

    async with connect(URI) as websocket:
        await send_log(websocket, "ears", "Подключился к хабу")
        await asyncio.gather(receiver(websocket, state), sender(websocket, state, listener))


if __name__ == "__main__":
    asyncio.run(main())