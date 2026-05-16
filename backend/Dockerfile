FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pydicom + pylibjpeg compressed-transfer-syntax support, plus curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e . -e ".[dev]"

# AI stack is optional and heavy (~1.5 GB). We install CPU-only torch
# and MONAI so `make seed-models` works out of the box; on networks
# where the PyTorch index is unreachable, the build still succeeds and
# the backend falls back to MockModel.
ARG INSTALL_AI=true
RUN if [ "$INSTALL_AI" = "true" ]; then \
        pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.3" \
        && pip install "monai>=1.3" \
        || echo "AI extras unavailable; MockModel will be used"; \
    fi

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
