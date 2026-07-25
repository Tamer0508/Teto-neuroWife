import asyncio
import json
from pathlib import Path
from websockets.asyncio.client import connect

VTS_URI = "ws://localhost:8001"
PLUGIN_NAME = "Neuro Teto"
DEVELOPER = "Tamerlan"
TOKEN_FILE = Path(__file__).parent / "vts_token.txt"

EMOTION_HOTKEYS = {
    "joy":         ["ebd026ebc2f64dd0835ded46b7170166"],                                      # Star Eye
    "neutral":     [],                                                                        # только сброс
    "embarrassed": ["c0549ee2d7f249db8aee00c4d7e7194a", "45a61cb1427148b1b0a75b01dbf89cdc"],  # Blush + Squint
    "smug":        ["a84778ab290f4090831ed1af4db174c5", "6736f0a7c5ca488d9027d5e88c77acdc"],  # Dark Face + Dark Eye
    "sad":         ["9e55efcfb583413981c5cadec484e5a1"],                                      # Cry
    "confused":    ["6e43e77a8dfe4b9f8416cf8f99299e01"],                                      # Dizzy Eye
    "pout":        ["45a61cb1427148b1b0a75b01dbf89cdc"],                                      # Squint Eye
}

RESET_HOTKEY = "29f2ed6a53074b6ab86c40b4260ab2d1"   # Remove All Toggles

PERSISTENT_HOTKEYS = [
    "550fe382f2a54c928a16603014dba5e6",   # Remove Water Mark
]


def request(message_type, data=None):
    return json.dumps({
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "neuro-teto",
        "messageType": message_type,
        "data": data or {},
    })


class VTS:
    def __init__(self):
        self.ws = None
        self.active = []

    async def connect(self):
        """Подключиться к VTube Studio и залогиниться сохранённым токеном."""
        token = TOKEN_FILE.read_text().strip()
        self.ws = await connect(VTS_URI)

        await self.ws.send(request("AuthenticationRequest", {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": DEVELOPER,
            "authenticationToken": token,
        }))

        resp = json.loads(await self.ws.recv())
        print(f"[vts] аутентификация: {resp['data']['authenticated']}")
        await self.trigger(RESET_HOTKEY)
        

    async def trigger(self, hotkey_id):
        """Нажать один хоткей."""
        await self.ws.send(request("HotkeyTriggerRequest", {"hotkeyID": hotkey_id}))
        await self.ws.recv()

    async def set_emotion(self, emotion):
        """Включить нужные тоглы, выключить лишние. Остальное не трогаем."""
        new = EMOTION_HOTKEYS.get(emotion, [])

        # гасим то, что горит, но в новой эмоции не нужно
        for hotkey in self.active:
            if hotkey not in new:
                await self.trigger(hotkey)
                await asyncio.sleep(0.05)

        # зажигаем то, что нужно, но ещё не горит
        for hotkey in new:
            if hotkey not in self.active:
                await self.trigger(hotkey)
                await asyncio.sleep(0.05)

        self.active = new

