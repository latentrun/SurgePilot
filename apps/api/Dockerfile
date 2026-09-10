FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG UV_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV UV_INDEX_URL=${UV_INDEX_URL}

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
COPY packages/contracts/runner/runner-callback.schema.json /opt/surgepilot/contracts/runner/runner-callback.schema.json

RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
