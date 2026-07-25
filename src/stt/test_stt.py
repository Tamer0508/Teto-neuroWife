import time
from listener import Listener

listener = Listener()

while True:
    print("\nГовори (Ctrl+C для выхода)...")
    audio = listener.listen()

    if audio is None:
        print("  [слишком коротко, пропускаю]")
        continue

    t0 = time.perf_counter()
    text = listener.transcribe(audio)
    print(f"{time.perf_counter() - t0:.2f}s -> {text}")