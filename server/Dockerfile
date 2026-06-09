FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (curl, plus Node for the Claude Code CLI).
# The agent_sdk LLM backend (claude-agent-sdk) shells out to the `claude`
# CLI binary, so it must be on PATH in the runtime image; the SDK then
# authenticates the CLI headlessly via the CLAUDE_CODE_OAUTH_TOKEN env var
# (set on Railway). CLI version pinned to match the SDK's bundled version.
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @anthropic-ai/claude-code@2.1.165 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY ./pyproject.toml ./uv.lock /app/

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY . /app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Add uv virtual env to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run the application
CMD uvicorn dars.main:app --host 0.0.0.0 --port ${PORT:-8000}
