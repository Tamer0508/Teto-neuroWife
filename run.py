import subprocess
import sys
import time
import socket
from pathlib import Path

ROOT = Path(__file__).parent

SERVICES = [
    ("hub",    ROOT / "src" / "hub",    "hub.py"),
    ("brain",  ROOT / "src" / "brain",  "brain_service.py"),
    ("tts",    ROOT / "src" / "tts",    "tts_service.py"),
    ("avatar", ROOT / "src" / "avatar", "avatar_service.py"),
    ("stt",    ROOT / "src" / "stt",    "stt_service.py"),
    ("server", ROOT / "src",            "server.py"),
]

CLIENT_DIR = ROOT / "src" / "client"
CLIENT_FILE = "console_client.py"


def wait_port(host, port, timeout=10):
    """Ждём, пока порт начнёт принимать соединения (хаб поднялся)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


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

            # хаб должен успеть открыть порт, прежде чем остальные к нему полезут
            if name == "hub":
                if wait_port("localhost", 8765):
                    print("[run] хаб готов")
                else:
                    print("[run] хаб не поднялся за 10с — продолжаю на свой страх")
            else:
                time.sleep(2)

        print("[run] запускаю консоль\n")
        subprocess.run([sys.executable, CLIENT_FILE], cwd=CLIENT_DIR)

    finally:
        print("\n[run] останавливаю сервисы...")
        for process in processes:
            process.terminate()


if __name__ == "__main__":
    main()