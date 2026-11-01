# The UI bundle is platform-independent, so it is built once natively even for multi-arch images
FROM --platform=$BUILDPLATFORM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JOBTRACE_HOME=/data \
    JOBTRACE_HOST=0.0.0.0 \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --no-cache-dir --default-timeout=100 --retries 5 -r backend/requirements.txt

COPY backend/ backend/
COPY config.example.yaml .env.example ./
COPY --from=web /web/dist frontend/dist

# Version stamps go last so a new release does not invalidate the dependency layers
ARG JOBTRACE_VERSION=dev
ARG JOBTRACE_COMMIT=
LABEL org.opencontainers.image.title="JobTrace" \
      org.opencontainers.image.description="Self-hosted job tracker with Telegram alerts" \
      org.opencontainers.image.source="https://github.com/mr-anjaneyam/JobTrace" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="$JOBTRACE_VERSION" \
      org.opencontainers.image.revision="$JOBTRACE_COMMIT"
ENV JOBTRACE_VERSION=$JOBTRACE_VERSION \
    JOBTRACE_COMMIT=$JOBTRACE_COMMIT

RUN useradd --create-home --uid 1000 jobtrace \
    && mkdir /data \
    && chown jobtrace:jobtrace /data
USER jobtrace

WORKDIR /app/backend
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8).status == 200 else 1)"

CMD ["python", "-m", "jobtrace.main", "web", "--port", "8000"]
