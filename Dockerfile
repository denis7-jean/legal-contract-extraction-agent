# Stage 1 — builder
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --upgrade pip \
    && pip install build \
    && python -m build --wheel --outdir /build/dist

# Stage 2 — runtime
FROM python:3.11-slim AS runtime
WORKDIR /app

# Create non-root user for security
RUN addgroup --system legal && adduser --system --group legal

# Copy wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && pip install --no-cache-dir "uvicorn[standard]>=0.29.0" \
    && rm /tmp/*.whl

# Copy only what runtime needs
COPY src/ src/

# Switch to non-root user
USER legal

# Environment defaults — override at runtime
ENV PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006/v1/traces
ENV PORT=8000

EXPOSE 8000

# Health check — hits our /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["sh", "-c", "uvicorn legal_agent.api.main:app --host 0.0.0.0 --port ${PORT}"]
