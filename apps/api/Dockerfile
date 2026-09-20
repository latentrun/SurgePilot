FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG UV_INDEX_URL=https://pypi.org/simple
ARG SURGEPILOT_VERSION=dev
ARG SURGEPILOT_PRODUCT_VERSION
ARG SURGEPILOT_REVISION=unknown
ARG SURGEPILOT_SOURCE=https://github.com/latentrun/SurgePilot
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV UV_INDEX_URL=${UV_INDEX_URL}
ENV SURGEPILOT_PRODUCT_VERSION=${SURGEPILOT_PRODUCT_VERSION}

LABEL org.opencontainers.image.source=${SURGEPILOT_SOURCE} \
      org.opencontainers.image.revision=${SURGEPILOT_REVISION} \
      org.opencontainers.image.version=${SURGEPILOT_VERSION}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/app ./app
COPY apps/api/migrations ./migrations
COPY apps/runner /opt/surgepilot/runner-bundle
COPY packages/ai-skills/surgepilot-public-api /opt/surgepilot/ai-skills/surgepilot-public-api
COPY packages/contracts/runner/runner-callback.schema.json /opt/surgepilot/contracts/runner/runner-callback.schema.json
COPY scripts/bootstrap_deployment_env.py /opt/surgepilot/release-tools/bootstrap_deployment_env.py
COPY scripts/release_preflight.py /opt/surgepilot/release-tools/release_preflight.py
COPY scripts/fetch_runtime_release.py /opt/surgepilot/release-tools/fetch_runtime_release.py
COPY scripts/__init__.py /opt/surgepilot/release-tools/scripts/__init__.py
COPY scripts/release_preflight.py /opt/surgepilot/release-tools/scripts/release_preflight.py

RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
