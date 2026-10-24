# Multi-arch (amd64 and arm64, e.g. Oracle Cloud Ampere) image for the worker.
FROM python:3.12.8-slim-bookworm

RUN pip install --no-cache-dir uv==0.5.11

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --system --uid 10001 sharp
USER sharp

CMD ["sharp-eyes", "capture"]
