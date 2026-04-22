FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
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
