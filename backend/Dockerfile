FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir uv && uv sync --no-dev

COPY . /app
RUN uv sync --no-dev && chmod +x bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["bin/docker-entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

