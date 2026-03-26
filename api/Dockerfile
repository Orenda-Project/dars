FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Install dependencies first (cached layer — only invalidated when pyproject.toml changes)
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy app source (invalidates cache only on code changes, not dep changes)
COPY src/ src/

# Run the app
CMD ["uv", "run", "uvicorn", "dars.main:app", "--host", "0.0.0.0", "--port", "8000"]
