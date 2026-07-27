# hub_log.py
import json
import time


async def send_log(ws, sender, message, level="info"):
    # 1) всегда в консоль — работает даже если хаб лежит
    print(f"[{sender}] {message}")

    # 2) конверт по вашему протоколу; data — объект, так браузеру удобнее
    envelope = {
        "type": "log",
        "sender": sender,
        "data": {
            "level": level,          # info / warn / error
            "message": message,
            "ts": time.time(),       # для сортировки лога в браузере
        },
    }

    # 3) отправка в хаб; ошибку глотаем — сервис ронять нельзя
    try:
        if ws is not None:
            await ws.send(json.dumps(envelope, ensure_ascii=False))
    except Exception:
        pass