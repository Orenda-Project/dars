FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies (no dev deps in production image)
RUN uv sync --no-dev

# Run the app
CMD ["uv", "run", "uvicorn", "dars.main:app", "--host", "0.0.0.0", "--port", "8000"]
