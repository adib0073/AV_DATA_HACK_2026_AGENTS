"""Central configuration, loaded from environment / .env.

Everything that changes between "demo mode" and "fixed mode", or between
"direct MCP" and "gateway MCP", lives here so the rest of the code stays clean.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

# docker compose passes OPENAI_BASE_URL as an empty string when it isn't set in
# .env. The OpenAI SDK (used directly by DeepEval's LLM-as-judge) treats an empty
# OPENAI_BASE_URL as *the* base URL and fails every call with
# "Request URL is missing an 'http://' or 'https://' protocol". LangChain only
# applies base_url when truthy, so the agent worked while every judge metric
# silently errored. Drop the empty value so the SDK falls back to api.openai.com.
_base_url = os.environ.get("OPENAI_BASE_URL")
if _base_url is not None and not _base_url.strip():
    del os.environ["OPENAI_BASE_URL"]


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # --- LLM ---
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str | None = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL") or None
    )
    judge_model: str = field(
        default_factory=lambda: os.getenv("DEEPEVAL_JUDGE_MODEL", "gpt-4o")
    )

    # --- Token pricing (USD per 1M tokens) ---
    price_input_per_m: float = field(
        default_factory=lambda: float(os.getenv("PRICE_INPUT_PER_M", "0.15"))
    )
    price_output_per_m: float = field(
        default_factory=lambda: float(os.getenv("PRICE_OUTPUT_PER_M", "0.60"))
    )

    # --- MCP connectivity ---
    use_gateway: bool = field(default_factory=lambda: _bool("USE_MCP_GATEWAY", False))
    gateway_token: str = field(default_factory=lambda: os.getenv("MCP_GATEWAY_TOKEN", ""))

    # --- Demo controls ---
    inject_regression: bool = field(
        default_factory=lambda: _bool("INJECT_REGRESSION", False)
    )

    @property
    def cost_per_input_token(self) -> float:
        return self.price_input_per_m / 1_000_000.0

    @property
    def cost_per_output_token(self) -> float:
        return self.price_output_per_m / 1_000_000.0

    def mcp_connections(self) -> dict[str, dict]:
        """Build the MultiServerMCPClient connection map.

        In direct mode we point at the local FastMCP servers. In gateway mode we
        point at the Obot MCP gateway, which reverse-proxies the same upstream
        servers while emitting OTel traces for every tool call (Layer 4).
        """
        if self.use_gateway:
            urls = {
                "flights": os.getenv("MCP_GATEWAY_FLIGHTS_URL", "http://localhost:8080/mcp/flights"),
                "hotels": os.getenv("MCP_GATEWAY_HOTELS_URL", "http://localhost:8080/mcp/hotels"),
                "activities": os.getenv("MCP_GATEWAY_ACTIVITIES_URL", "http://localhost:8080/mcp/activities"),
                "booking": os.getenv("MCP_GATEWAY_BOOKING_URL", "http://localhost:8080/mcp/booking"),
            }
            headers = (
                {"Authorization": f"Bearer {self.gateway_token}"}
                if self.gateway_token
                else None
            )
        else:
            urls = {
                "flights": os.getenv("MCP_FLIGHTS_URL", "http://localhost:8001/mcp"),
                "hotels": os.getenv("MCP_HOTELS_URL", "http://localhost:8002/mcp"),
                "activities": os.getenv("MCP_ACTIVITIES_URL", "http://localhost:8003/mcp"),
                "booking": os.getenv("MCP_BOOKING_URL", "http://localhost:8004/mcp"),
            }
            headers = None

        connections: dict[str, dict] = {}
        for name, url in urls.items():
            conn: dict = {"url": url, "transport": "streamable_http"}
            if headers:
                conn["headers"] = headers
            connections[name] = conn
        return connections


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
