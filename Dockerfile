# clawithme — Docker image
FROM python:3.11-slim

ENV PIP_PREFER_BINARY=1

# System deps: libcurl + build tools for Scrapling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev libssl-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

# Runtime deps: pango/cairo for WeasyPrint PDF, CJK fonts for Chinese text
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libpangoft2-1.0 libpangocairo-1.0 shared-mime-info \
    fonts-noto fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install Python deps (all have pre-built ARM64 wheels)
RUN pip install --prefer-binary \
    scrapling fastapi uvicorn weasyprint slowapi \
    pydantic structlog Pillow jsonschema imagehash

# Install clawithme itself (pure Python, no compilation)
COPY . /app
WORKDIR /app
RUN pip install --no-deps -e .

EXPOSE 8000
ENTRYPOINT ["python", "-m", "clawithme.web.app"]
