import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent

SERVICES = [
    ("hub",   ROOT / "src" / "hub",    "hub.py"),
    ("brain", ROOT / "src" / "brain",  "brain_service.py"),
    ("tts",   ROOT / "src" / "tts",    "tts_service.py"),
    ("avatar", ROOT / "src" / "avatar", "avatar_service.py"),
    ("stt", ROOT / "src" / "stt", "stt_service.py"),
]

CLIENT_DIR = ROOT / "src" / "client"
CLIENT_FILE = "console_client.py"


def main():
    processes = []

    try:
        for name, folder, script in SERVICES:
            print(f"[run] запускаю {name}...")
            p = subprocess.Popen(
                ["cmd", "/k", sys.executable, script],
                cwd=folder,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            processes.append(p)
            time.sleep(2)

        print("[run] запускаю консоль\n")

        subprocess.run([sys.executable, CLIENT_FILE], cwd=CLIENT_DIR)

    finally:
        print("\n[run] останавливаю сервисы...")
        for process in processes:
            process.terminate()

if __name__ == "__main__":
    main()