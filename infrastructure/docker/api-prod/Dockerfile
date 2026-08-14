# services/api (RestaurantOS API) -- production image.
#
# Companion to infrastructure/docker/api/Dockerfile, which is explicitly
# dev-only (bind-mounted source, --reload, runs as root). This image is
# what docker-compose.prod.yml (repo root) actually runs: immutable
# (source baked in, no bind mount), non-root, no --reload, multi-stage to
# keep the runtime image free of compilers/build headers.
#
# Written for RestaurantOS Phase 1 (Release/Deployment) -- see
# docs/RestaurantOS_Production_Deployment_Guide.md.

# ---- builder ---------------------------------------------------------
FROM python:3.13-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src

# Editable installs don't survive being copied to another image (the
# egg-link points at a path that won't exist there) -- build a real
# wheel instead, matching the standard multi-stage pattern.
RUN pip install --no-cache-dir build && python -m build --wheel

# ---- runtime -----------------------------------------------------------
FROM python:3.13-slim AS runtime

# libpq itself (not -dev/headers -- nothing compiles in this stage).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin restaurantos

WORKDIR /app
COPY --from=builder /build/dist/*.whl /tmp/
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

USER restaurantos
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/health/live || exit 1

# Migrations run once at container start, before uvicorn binds -- see
# docker-compose.prod.yml's own comment on why this is safe for a
# single-instance pilot deploy (not safe unmodified for >1 replica; see
# the deployment guide's "Updating RestaurantOS" section).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn restaurant_os_api.main:app --host 0.0.0.0 --port 8000 --workers 2"]
