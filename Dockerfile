# clawithme — Docker image
FROM python:3.11-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    DEBIAN_FRONTEND=noninteractive

# ── Optional API tokens ──
# Discord Bot Token for Discord profile extraction
# ENV DISCORD_BOT_TOKEN=

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

WORKDIR /app

# Install dependencies before copying source so code-only changes reuse this layer.
COPY pyproject.toml README.md /app/
RUN pip install --prefer-binary ".[web]"
RUN playwright install --with-deps chromium

# Install clawithme itself (pure Python, no compilation)
COPY . /app
RUN pip install --no-deps -e .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"
ENTRYPOINT ["python", "-m", "clawithme.web.app"]
