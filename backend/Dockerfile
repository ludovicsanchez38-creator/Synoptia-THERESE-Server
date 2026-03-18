FROM python:3.12-slim

WORKDIR /app

# Dependances systeme (compilateur C pour les packages natifs, libpq pour PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Dependances Python - installees avant le code pour profiter du cache Docker
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings sqlmodel \
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

# Copier le code source
COPY . .

# Repertoire de donnees persistantes
RUN mkdir -p /var/lib/therese

EXPOSE 8000

# Healthcheck integre
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
