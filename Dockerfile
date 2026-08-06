# Local-testing image: Python + libmariadb + pip deps. Source is mounted at runtime.

FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmariadb-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps before copying source so the layer caches across edits.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
