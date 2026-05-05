# Local-testing image for the Smash Ranking script.
# Bundles Python + the C client libs needed for the `mariadb` Python driver
# + the project's pip requirements. Source code is mounted at runtime via
# docker-compose so edits are picked up without rebuilding.

FROM python:3.13-slim

# libmariadb-dev: header + .so for the mariadb python connector to compile/link.
# build-essential: gcc/make for the connector's C extension.
# pkg-config: connector setup looks it up to find libmariadb.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmariadb-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python deps first so the layer caches across source changes.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Source is mounted at runtime via docker-compose (not COPY'd) so iteration
# doesn't require rebuilding the image.
CMD ["python", "app.py"]
