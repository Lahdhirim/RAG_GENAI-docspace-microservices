FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory for the application
WORKDIR /app

# uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy application code and install dependencies
COPY . .
RUN uv sync --package parser_service --no-dev

# Change working directory
WORKDIR /app/src/services/parser_service

# Run the application using uvicorn
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]