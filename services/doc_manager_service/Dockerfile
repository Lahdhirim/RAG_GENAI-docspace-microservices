FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY . .
RUN uv sync

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]