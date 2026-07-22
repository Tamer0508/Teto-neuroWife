import asyncio
import json
from websockets.asyncio.client import connect

VTS_URI = "ws://localhost:8001"
PLUGIN_NAME = "Neuro Teto"
DEVELOPER = "Tamerlan"
TOKEN_FILE = "vts_token.txt"


def request(message_type, data=None):
    """Собирает конверт в формате VTube Studio API."""
    return json.dumps({
        "apiName": "VTubeStudioPublicAPI",
        "apiVersion": "1.0",
        "requestID": "neuro-teto",
        "messageType": message_type,
        "data": data or {},
    })


async def main():
    async with connect(VTS_URI) as ws:
        # 1. Запрашиваем токен — VTS покажет окно подтверждения
        await ws.send(request("AuthenticationTokenRequest", {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": DEVELOPER,
        }))
        print(">>> Подтверди доступ в окне VTube Studio! <<<")

        resp = json.loads(await ws.recv())
        token = resp["data"]["authenticationToken"]

        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"[vts] токен сохранён в {TOKEN_FILE}")

        # 2. Логинимся полученным токеном
        await ws.send(request("AuthenticationRequest", {
            "pluginName": PLUGIN_NAME,
            "pluginDeveloper": DEVELOPER,
            "authenticationToken": token,
        }))
        resp = json.loads(await ws.recv())
        print(f"[vts] аутентификация: {resp['data']['authenticated']}")

        # 3. Получаем список хоткеев текущей модели
        await ws.send(request("HotkeysInCurrentModelRequest"))
        resp = json.loads(await ws.recv())

        print("\n--- Хоткеи модели ---")
        for hk in resp["data"]["availableHotkeys"]:
            print(f'{hk["name"]!r:35} -> {hk["hotkeyID"]}')


if __name__ == "__main__":
    asyncio.run(main())