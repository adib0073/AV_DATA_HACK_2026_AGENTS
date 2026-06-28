"""Launch all four mock MCP servers as subprocesses (cross-platform).

Usage:  python mcp_servers/run_all.py
Press Ctrl+C to stop them all.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SERVERS = [
    ("flights",    "flights_server.py",    8001),
    ("hotels",     "hotels_server.py",     8002),
    ("activities", "activities_server.py", 8003),
    ("booking",    "booking_server.py",    8004),
]


def main() -> int:
    procs = []
    print("Starting mock MCP servers...\n")
    for name, script, port in SERVERS:
        p = subprocess.Popen([sys.executable, str(HERE / script)], cwd=str(HERE))
        procs.append((name, port, p))
        print(f"  - {name:11s} -> http://127.0.0.1:{port}/mcp  (pid {p.pid})")
        time.sleep(0.5)

    print("\nAll servers running. Press Ctrl+C to stop.\n")

    def shutdown(*_):
        print("\nStopping servers...")
        for _, _, p in procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    try:
        while True:
            time.sleep(1)
            for name, port, p in procs:
                if p.poll() is not None:
                    print(f"[warn] {name} (:{port}) exited with code {p.returncode}")
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
