import asyncio
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

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
            # рассылаем всем, КРОМЕ отправителя.
            # дохлый клиент НЕ должен срывать доставку остальным — оборачиваем каждый send.
            for client in list(clients):
                if client is websocket:
                    continue
                try:
                    await client.send(message)
                except Exception:
                    clients.discard(client)      # клиент отвалился — убираем, идём дальше

    except ConnectionClosed:
        pass                                     # клиент закрылся резко — это норма, хаб не роняем
    except Exception as e:
        print(f"[hub] ошибка соединения: {e}")
    finally:
        clients.discard(websocket)
        print(f"[hub] клиент отключился, всего: {len(clients)}")


async def main():
    async with serve(handler, HOST, PORT):
        print(f"[hub] запущен на ws://{HOST}:{PORT}")
        await asyncio.Future()          # держит сервер живым бесконечно


if __name__ == "__main__":
    asyncio.run(main())