import asyncio
from websockets.asyncio.server import serve

HOST = "localhost"
PORT = 8765

# Множество всех подключённых клиентов
clients = set()


async def handler(websocket):
    """Вызывается ОДИН раз на каждое новое подключение и живёт, пока клиент подключён."""

    clients.add(websocket)
    print(f"[hub] клиент подключился, всего: {len(clients)}")

    try:
        async for message in websocket:
            for client in list(clients):
                if client is not websocket:
                    await client.send(message)

    finally:
        clients.remove(websocket)


async def main():
    async with serve(handler, HOST, PORT):
        print(f"[hub] запущен на ws://{HOST}:{PORT}")
        await asyncio.Future()          # держит сервер живым бесконечно


if __name__ == "__main__":
    asyncio.run(main())