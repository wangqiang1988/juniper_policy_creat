# Multi-stage build: builder compiles deps, runtime only carries the venv + source.

# ---------- Stage 1: build the virtualenv ----------
FROM python:3.12-slim AS builder

# Install uv (pinned version for reproducible builds)
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

# Workdir inside the image
WORKDIR /app

# Copy only what uv needs first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Build the venv at /app/.venv (system-level, not project env)
# --no-install-project: install deps only, not the project itself
# --frozen: respect uv.lock exactly (no resolution)
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself (no deps, just the package)
COPY juniper_policy_generator ./juniper_policy_generator
COPY app.py ./
RUN uv sync --frozen --no-dev

# ---------- Stage 2: minimal runtime image ----------
FROM python:3.12-slim AS runtime

# Copy uv from builder so we can run `uv run` / `uv pip`
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy the prebuilt venv and project files
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/juniper_policy_generator /app/juniper_policy_generator
COPY --from=builder /app/app.py /app/app.py

# Make sure we use the venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run as non-root
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Health check hits the lightweight /health endpoint added in app.py
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else sys.exit(1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
