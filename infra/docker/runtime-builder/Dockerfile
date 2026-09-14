FROM python:3.12-slim-bookworm

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG UV_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV UV_INDEX_URL=${UV_INDEX_URL}
ENV UV_PROJECT_ENVIRONMENT=/tmp/surgepilot-runtime-builder-venv
ENV UV_FROZEN=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        openjdk-17-jre-headless \
        procps \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /workspace

COPY uv.lock pyproject.toml ./
COPY scripts/release_runtime_artifact.py ./scripts/release_runtime_artifact.py
COPY apps/runner/pyproject.toml ./apps/runner/pyproject.toml
COPY apps/runner/surgepilot_runner/jmeter_wrapper.py ./apps/runner/surgepilot_runner/jmeter_wrapper.py
COPY infra/docker/runtime-builder/Dockerfile ./infra/docker/runtime-builder/Dockerfile

ENTRYPOINT []
