import subprocess
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent

SERVICES = {
    "rooms_service": {
        "path": ROOT / "rooms_service",
        "port": 8080,
        "cmd": ["uv", "run", "python", "run.py"],
    },
    "users_service": {
        "path": ROOT / "users_service",
        "port": 8081,
        "cmd": ["uv", "run", "python", "run.py"],
    },
    "bookings_service": {
        "path": ROOT / "bookings_service",
        "port": 8082,
        "cmd": ["uv", "run", "python", "run.py"],
    },
    "orders_service": {
        "path": ROOT / "orders_service",
        "port": 8083,
        "cmd": ["uv", "run", "python", "run.py"],
    },
    "menu_service": {
        "path": ROOT / "menu_service",
        "port": 8084,
        "cmd": ["uv", "run", "python", "run.py"],
    },
}


def start_services():
    processes = []

    for name, config in SERVICES.items():
        print(f"Starting {name} on port {config['port']}...")
        proc = subprocess.Popen(
            config["cmd"],
            cwd=config["path"],
        )
        processes.append((name, proc))

    print("\nAll services started.")
    print("Press Ctrl+C to stop everything.\n")

    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"{name} stopped unexpectedly with code {proc.returncode}")
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for name, proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        for name, proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("All services stopped.")


if __name__ == "__main__":
    start_services()