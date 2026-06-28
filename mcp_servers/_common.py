"""Shared helpers for the mock MCP servers.

These servers are deliberately offline & deterministic: results are generated
from a seed derived from the inputs, so the same query always returns the same
options (great for repeatable demos and golden datasets) while still looking
realistic for any destination the speaker types on stage.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def mcp_host() -> str:
    """Bind address for the FastMCP servers.

    Defaults to 127.0.0.1 for local runs; set MCP_HOST=0.0.0.0 in containers so
    other services on the Docker network can reach them.
    """
    return os.getenv("MCP_HOST", "127.0.0.1")


def load_json(name: str, default):
    path = DATA_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def seeded_rng(*parts: object) -> random.Random:
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def city_code(city: str) -> str:
    letters = [c for c in (city or "XXX").upper() if c.isalpha()]
    return ("".join(letters) + "XXX")[:3]
