FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends     gcc     libpq-dev     && rm -rf /var/lib/apt/lists/*

# Installer UV pour la gestion des dépendances
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copier les dépendances
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml 2>/dev/null || uv pip install --system .

# Copier le code
COPY . .

# Port
EXPOSE 8000

# Lancer
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
