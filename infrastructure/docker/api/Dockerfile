# services/api (RestaurantOS API) -- local development image.
#
# Optimized for hot-reload dev, not a production artifact: source is bind-
# mounted over this image by docker-compose.yml (see WORKDIR below), and
# uvicorn runs with --reload. A separate production-shaped image (immutable,
# no reload, non-root, multi-stage-trimmed) is deferred until an actual
# staging/production deployment target exists -- see docs/RELEASE_CHECKLIST.md.
FROM python:3.13-slim

# libpq (asyncpg builds its own C extension, but psycopg-style tooling and
# some transitive deps still expect libpq headers at build time) + build
# essentials for any package that needs to compile.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Source must be present *before* the editable install: setuptools'
# PEP 660 editable install only maps the files it can see in the
# package directory (src/restaurant_os_api) at install time -- with
# only pyproject.toml copied in, `pip install -e .` "succeeds" (it
# builds an editable wheel with zero mapped files) but the package is
# permanently unimportable even after src/ is copied in afterward.
# Confirmed by reproducing this exact two-step sequence outside Docker.
# Costs the dependency-layer-caching optimization a naive COPY-order
# would give (editing application code now invalidates this layer too),
# but the image must actually build and run correctly first. Overwritten
# by docker-compose.yml's bind mount in dev either way; present here so
# the image is still runnable standalone (`docker build` + `docker run`).
COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "restaurant_os_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
