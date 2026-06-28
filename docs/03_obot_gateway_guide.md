# 03 · Obot guide — Layer 4 + the AI-gateway / cost question

## What Obot is

[Obot](https://github.com/obot-platform/obot) is an **open-source MCP platform**:
hosting, registry, **MCP gateway**, and a chat client. For this talk we care about
two capabilities:

1. **MCP gateway** — a reverse-proxy passthrough between MCP clients (our agent)
   and MCP servers. It authenticates, authorizes, **audit-logs every tool call**,
   and gives usage visibility — *without changing the agent or the servers*. This
   is **Layer 4: codeless observability**.
2. **LLM proxy (AI gateway)** — Obot can sit in front of the LLM and track
   **realized USD spend** per model / per user, normalizing input + output +
   cached + thinking tokens (pricing defaults to `models.dev`). This answers your
   "can it act as an AI gateway showing token consumption + cost?" question.

---

## Your question, answered directly

> **Can Obot or DeepEval be used as an AI gateway that also shows token
> consumption, estimated cost, etc.?**

| | Obot | DeepEval + Confident AI |
|---|---|---|
| Network **gateway/proxy** for LLM calls? | **Yes** — LLM proxy | No — it's instrumentation |
| Network **gateway/proxy** for MCP/tool calls? | **Yes** — MCP gateway | No |
| Token usage tracking | **Yes** (codeless, at the proxy) | Yes (per `@observe` LLM span) |
| **USD cost** tracking | **Yes** — realized spend per model/user | Yes — per span, summed per trace |
| Eval metrics (task success, tool correctness…) | No | **Yes** — this is its core |
| Best role in this stack | **Layers 4** (codeless tool + LLM visibility) | **Layers 1–3** (eval + in-code traces) |

**Bottom line:**
- Use **Obot as the gateway** — both for MCP tool calls (codeless Layer 4) and,
  optionally, as an **AI gateway** that meters LLM token spend in USD.
- Use **DeepEval/Confident AI for evaluation + in-code tracing** (Layers 1–3).
  It *does* track token cost, but as instrumentation, not as a network gateway.

They're complementary: Obot covers *what you don't own / didn't instrument*;
DeepEval covers *what you own and want to score*. Both can correlate by trace id.

---

## Run Obot (Docker)

```bash
# OPENAI_API_KEY and OBOT_BOOTSTRAP_TOKEN should be in your environment / .env
docker compose -f config/obot/docker-compose.yml up -d
docker logs obot          # find the bootstrap token
# open http://localhost:8080  and log in with the token
```

(Or the raw command from the Obot docs:)

```bash
docker run -d --name obot -p 8080:8080 \
  -v obot-data:/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e OBOT_SERVER_ENABLE_AUTHENTICATION=true \
  -e OBOT_BOOTSTRAP_TOKEN=changeme-bootstrap \
  ghcr.io/obot-platform/obot:latest
```

---

## Wire the mock MCP servers behind Obot (Layer 4)

1. Keep the mock servers running on the host: `python mcp_servers/run_all.py`.
2. In the Obot admin UI → **MCP Servers → add a remote server** for each:
   - flights → `http://host.docker.internal:8001/mcp`
   - hotels → `http://host.docker.internal:8002/mcp`
   - activities → `http://host.docker.internal:8003/mcp`
   - booking → `http://host.docker.internal:8004/mcp`
   > On Windows/Mac Docker Desktop, the container reaches the host via
   > `host.docker.internal`. On native Linux use the host IP or `--network=host`.
3. Obot gives each server a **gateway connection URL**. Copy those into `.env`:
   ```
   USE_MCP_GATEWAY=true
   MCP_GATEWAY_FLIGHTS_URL=<paste from Obot>
   MCP_GATEWAY_HOTELS_URL=<paste from Obot>
   MCP_GATEWAY_ACTIVITIES_URL=<paste from Obot>
   MCP_GATEWAY_BOOKING_URL=<paste from Obot>
   MCP_GATEWAY_TOKEN=<token if the gateway requires a bearer>
   ```
4. Restart the agent. **No code changed** — yet every tool call now shows up in
   Obot's audit log / usage view. That's the Layer 4 "magic moment."

> The exact gateway URL shape is owned by your Obot version — always copy the URL
> Obot shows you rather than hand-constructing it. The placeholders in
> `.env.example` are illustrative.

---

## Use Obot as the AI gateway (token + USD cost, codeless)

To meter LLM spend without touching agent code, point the OpenAI client at Obot's
LLM proxy:

```
# .env
OPENAI_BASE_URL=<Obot LLM proxy base URL, e.g. http://localhost:8080/llm/v1>
```

`src/trip_planner/llm.py` already passes `base_url` through to `ChatOpenAI`, so
the *same agent* now routes its calls via Obot. Obot records tokens (input/output/
cached/thinking) and computes realized USD spend per model/user in its admin UI.

> Confirm the exact proxy path/version in your Obot build; the LLM-proxy + USD
> spend accounting landed in Obot in 2026 (`pkg/gateway/server/llmproxy.go`).
> If your build predates it, use the MCP gateway for Layer 4 and rely on
> DeepEval/Confident AI for token cost.

---

## Trade-offs (be honest on stage)

- One extra network hop → small latency cost.
- The gateway becomes a critical dependency → treat it like any gateway (HA,
  health checks, blue/green).
- You still own auth + TLS termination correctly.

## Alternatives (same pattern, different box)

IBM ContextForge · MCPJungle · Docker MCP Gateway · Lunar MCPX · Envoy AI
Gateway. For an **AI gateway** specifically (LLM token/cost metering): Obot LLM
proxy, LiteLLM, Helicone, Cloudflare AI Gateway. The architecture in this repo is
gateway-agnostic — only `OPENAI_BASE_URL` and the `MCP_GATEWAY_*` URLs change.
