"""
Thérèse Server - FastAPI Application

Assistant IA multi-utilisateurs pour collectivités et PME.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

# Rate limiting (SEC-015)
from app.rate_limit import HAS_SLOWAPI, limiter

try:
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
except ImportError:
    pass

from app.auth.backend import decode_access_token
from app.models.database import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("Thérèse Server %s démarrage...", settings.app_version)

    # Importer les modèles auth pour les enregistrer
    from app.auth import models as auth_models  # noqa: F401

    # Initialiser la base de données
    await init_db()
    logger.info("Base de données initialisée")

    # Initialiser Qdrant si configuré
    skip_services = os.environ.get("THERESE_SKIP_SERVICES") == "1"
    if not skip_services:
        try:
            from app.services import init_qdrant

            await init_qdrant()
            logger.info("Qdrant initialisé")
        except (ConnectionError, OSError, ImportError) as e:
            logger.warning("Qdrant non disponible (mode dégradé) : %s", e)

    yield

    # Shutdown
    await close_db()
    try:
        from app.services.http_client import close_http_client
        await close_http_client()
    except Exception:
        pass
    if not skip_services:
        try:
            from app.services import close_qdrant

            await close_qdrant()
        except Exception as e:
            logger.debug("Qdrant shutdown cleanup: %s", e)

    logger.info("Thérèse Server arrêté")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## Thérèse Server - API REST

Assistant IA multi-utilisateurs pour collectivités et PME.

### Authentification

Tous les endpoints (sauf /health et /api/auth/login) nécessitent un token JWT.

```
Authorization: Bearer <token>
```

### Rôles

| Rôle | Description | Accès |
|-------|-------------|-------|
| admin | DSI, administrateur | Tout |
| manager | Chef de service | Chat, contacts, config |
| agent | Utilisateur standard | Chat, contacts |

### Multi-tenant

Chaque utilisateur ne voit que ses propres données.
Les admins voient les utilisateurs de leur organisation.
""",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS - configurable par environnement
    origins = ["http://localhost:3000", "http://localhost:5173"]
    if settings.domain != "localhost":
        origins.append(f"https://{settings.domain}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting
    if HAS_SLOWAPI:
        app.state.limiter = limiter
        app.add_middleware(SlowAPIMiddleware)

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
            return JSONResponse(
                status_code=429,
                content={"detail": "Trop de requêtes. Réessayez dans quelques instants."},
            )


    # Security headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # Auth middleware global (SEC-001) - JWT requis pour /api/* sauf routes publiques
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        # Routes publiques (pas de JWT requis)
        public_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/auth/login",
            "/api/auth/refresh",
        ]
        if any(path.startswith(p) for p in public_paths) or not path.startswith("/api/"):
            return await call_next(request)

        # Verifier le token JWT
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token d'authentification requis"},
            )

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
            if not payload:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token invalide ou expire"},
                )
            request.state.user_id = payload.get("sub")
            request.state.user_role = payload.get("role")
            request.state.org_id = payload.get("org_id")
        except (ValueError, KeyError) as e:
            logger.debug("Token decode failed: %s", e)
            return JSONResponse(
                status_code=401,
                content={"detail": "Token invalide ou expire"},
            )

        return await call_next(request)

    # Error handlers
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)},
        )

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": settings.app_version}

    @app.get("/health/services")
    async def health_services():
        services = {"database": "ok", "qdrant": "unknown"}
        try:
            from app.models.database import get_session_context

            async with get_session_context() as session:
                from sqlmodel import text

                await session.execute(text("SELECT 1"))
        except (ConnectionError, OSError) as e:
            services["database"] = f"error: {e}"

        try:
            from app.services.qdrant import get_qdrant_client

            client = get_qdrant_client()
            if client:
                await client.get_collections()
                services["qdrant"] = "ok"
        except (ConnectionError, OSError) as e:
            services["qdrant"] = f"error: {e}"

        return {"status": "ok", "services": services}

    # Register routers
    from app.auth.router import router as auth_router
    app.include_router(auth_router)

    # Routers adaptés multi-user (P0-4)
    from app.routers.chat import router as chat_router
    app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

    from app.routers.chat_llm import router as chat_llm_router
    app.include_router(chat_llm_router, prefix="/api/chat", tags=["chat-llm"])

    from app.routers.memory import router as memory_router
    app.include_router(memory_router, prefix="/api/memory", tags=["memory"])

    from app.routers.config import router as config_router
    app.include_router(config_router, prefix="/api/config", tags=["config"])

    from app.routers.admin import router as admin_router
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

    from app.routers.agents import router as agents_router
    app.include_router(agents_router, prefix="/api/agents", tags=["agents"])

    from app.routers.rgpd import router as rgpd_router
    app.include_router(rgpd_router, prefix="/api/rgpd", tags=["rgpd"])

    from app.routers.templates import router as templates_router
    app.include_router(templates_router, prefix="/api/templates", tags=["templates"])

    from app.routers.files import router as files_router
    app.include_router(files_router, prefix="/api/files", tags=["files"])

    # --- P1 : Routers actives (rattrapage desktop) ---

    from app.routers.tasks import router as tasks_router
    app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"])

    from app.routers.crm import router as crm_router
    app.include_router(crm_router, prefix="/api/crm", tags=["crm"])

    from app.routers.commands import router as commands_router
    app.include_router(commands_router, prefix="/api/commands", tags=["commands"])

    from app.routers.commands_v3 import router as commands_v3_router
    app.include_router(commands_v3_router, prefix="/api/v3/commands", tags=["commands-v3"])

    from app.routers.data import router as data_router
    app.include_router(data_router, prefix="/api/data", tags=["data"])

    from app.routers.calculators import router as calculators_router
    app.include_router(calculators_router, prefix="/api/calc", tags=["calculators"])

    from app.routers.performance import router as performance_router
    app.include_router(performance_router, prefix="/api/perf", tags=["performance"])

    from app.routers.personalisation import router as personalisation_router
    app.include_router(personalisation_router, prefix="/api/personalisation", tags=["personalisation"])

    try:
        from app.routers.board import router as board_router
        app.include_router(board_router, prefix="/api/board", tags=["board"])
    except (ImportError, AttributeError) as e:
        logger.warning("Router board disabled: %s", e)

    try:
        from app.routers.invoices import router as invoices_router
        app.include_router(invoices_router, prefix="/api/invoices", tags=["invoices"])
    except (ImportError, AttributeError) as e:
        logger.warning("Router invoices disabled: %s", e)

    try:
        from app.routers.skills import router as skills_router
        app.include_router(skills_router, prefix="/api/skills", tags=["skills"])
    except (ImportError, AttributeError) as e:
        logger.warning("Router skills disabled: %s", e)

    # Recherche globale

    # Missions autonomes (agents)
    from app.routers.missions import router as missions_router
    app.include_router(missions_router, prefix="/api/missions", tags=["missions"])
    from app.routers.search import router as search_router
    app.include_router(search_router)

    return app


# Create app instance
app = create_app()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
