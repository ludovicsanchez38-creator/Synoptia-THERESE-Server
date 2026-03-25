# ============================================================
# Stage 1 : Builder - compilation des deps natives
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev && rm -rf /var/lib/apt/lists/*

# PyTorch CPU only (evite les 2GB de CUDA)
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    torch --no-deps

RUN pip install --no-cache-dir --prefix=/install \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    fastapi "uvicorn[standard]" pydantic pydantic-settings sqlmodel \
    aiosqlite asyncpg psycopg2-binary greenlet alembic \
    bcrypt "python-jose[cryptography]" \
    httpx python-multipart aiofiles pyyaml \
    slowapi "python-json-logger" \
    anthropic openai "google-genai" \
    qdrant-client sentence-transformers einops \
    python-docx python-pptx openpyxl reportlab \
    pypdf python-magic Pillow cryptography \
    beautifulsoup4 google-auth google-auth-oauthlib \
    google-auth-httplib2 google-api-python-client \
    imap-tools aiosmtplib caldav icalendar pytz

# ============================================================
# Stage 2 : Runtime - image finale legere
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# Deps runtime uniquement (pas de compilateur)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libmagic1 && rm -rf /var/lib/apt/lists/*

# Copier les packages Python depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source
COPY . .

# Repertoire de donnees persistantes
RUN mkdir -p /var/lib/therese

# User non-root
RUN useradd -r -s /bin/false therese && chown -R therese:therese /var/lib/therese
USER therese

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "3"]
