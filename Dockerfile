# Python image shared by the agent API and the four mock MCP servers.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY server ./server
COPY mcp_servers ./mcp_servers
COPY evals ./evals
COPY scripts ./scripts
COPY app ./app
COPY pyproject.toml README.md ./

EXPOSE 8000 8001 8002 8003 8004

# Default command runs the API; MCP services override `command` in compose.
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
