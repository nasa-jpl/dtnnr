# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM python:3.14-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /bin/uv

RUN adduser --disabled-password nonroot
RUN mkdir /home/app/ && chown -R nonroot:nonroot /home/app
WORKDIR /home/app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/home/app/.venv/bin:$PATH"

EXPOSE 5000

FROM base AS development
USER nonroot

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

CMD ["granian", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--interface", "asgi", \
     "--reload", \
     "app.asgi:app"]

FROM base AS production
USER nonroot

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

CMD ["granian", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--interface", "asgi", \
     "app.asgi:app"]
