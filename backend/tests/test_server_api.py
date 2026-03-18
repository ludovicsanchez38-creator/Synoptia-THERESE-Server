"""
Thérèse Server - Tests API

Tests d'intégration pour les endpoints serveur avec authentification JWT.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from app.auth.backend import hash_password, create_access_token, verify_password
from app.auth.models import Organization, User, UserRole, AuditLog, RefreshToken
from app.models.entities import Conversation, Message, Contact, Project, Preference, PromptTemplate


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app():
    """Create test FastAPI app."""
    import os
    os.environ["THERESE_SKIP_SERVICES"] = "1"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test-api.db"
    os.environ["DATA_DIR"] = "/tmp/therese-test-data"
    os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
    os.environ["SECRET_KEY"] = "test-secret-key"

    # Reset cached settings
    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app):
    """Create test client."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(app):
    """Initialize and cleanup database for each test."""
    import asyncio
    from app.models.database import init_db, close_db

    asyncio.get_event_loop().run_until_complete(init_db())
    yield
    asyncio.get_event_loop().run_until_complete(close_db())

    import os
    for f in ["test-api.db", "test-api.db-shm", "test-api.db-wal"]:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass


@pytest.fixture
def seed_org_and_admin(client, setup_db):
    """Seed an org + admin user and return (org, user, token)."""
    import asyncio
    from app.models.database import get_session_context

    async def _seed():
        async with get_session_context() as session:
            org = Organization(name="Test Org", slug="test-org", max_users=50)
            session.add(org)
            await session.flush()

            admin = User(
                email="admin@test.org",
                hashed_password=hash_password("admin123"),
                name="Admin Test",
                role=UserRole.ADMIN.value,
                org_id=org.id,
                is_active=True,
                is_verified=True,
                is_superuser=True,
                charter_accepted=True,
            )
            session.add(admin)
            await session.commit()
            await session.refresh(org)
            await session.refresh(admin)
            return org, admin

    org, admin = asyncio.get_event_loop().run_until_complete(_seed())
    token = create_access_token(admin)
    return org, admin, token


def auth_header(token: str) -> dict:
    """Create Authorization header."""
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# Auth Tests
# ============================================================

class TestAuth:
    """Tests authentification."""

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code in (200, 201)
        assert r.json()["status"] == "ok"

    def test_login_success(self, client, seed_org_and_admin):
        _, _, _ = seed_org_and_admin
        r = client.post(
            "/api/auth/login",
            data={"username": "admin@test.org", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, seed_org_and_admin):
        r = client.post(
            "/api/auth/login",
            data={"username": "admin@test.org", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    def test_login_unknown_user(self, client, seed_org_and_admin):
        r = client.post(
            "/api/auth/login",
            data={"username": "nobody@test.org", "password": "test"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 401

    def test_me_with_token(self, client, seed_org_and_admin):
        _, admin, token = seed_org_and_admin
        r = client.get("/api/auth/me", headers=auth_header(token))
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["email"] == "admin@test.org"
        assert data["role"] == "admin"
        assert data["org_name"] == "Test Org"

    def test_me_without_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_invalid_token(self, client):
        r = client.get("/api/auth/me", headers=auth_header("invalid-token"))
        assert r.status_code == 401


# ============================================================
# Chat Tests
# ============================================================

class TestChat:
    """Tests conversations et messages."""

    def test_create_conversation(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.post(
            "/api/chat/conversations",
            json={"title": "Ma conversation"},
            headers=auth_header(token),
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["title"] == "Ma conversation"
        assert data["message_count"] == 0

    def test_list_conversations(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        # Créer 2 conversations
        client.post("/api/chat/conversations", json={"title": "Conv 1"}, headers=auth_header(token))
        client.post("/api/chat/conversations", json={"title": "Conv 2"}, headers=auth_header(token))

        r = client.get("/api/chat/conversations", headers=auth_header(token))
        assert r.status_code in (200, 201)
        data = r.json()
        assert len(data) == 2

    def test_add_message(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        # Créer conversation
        conv = client.post(
            "/api/chat/conversations",
            json={"title": "Test messages"},
            headers=auth_header(token),
        ).json()

        # Ajouter un message
        r = client.post(
            f"/api/chat/conversations/{conv['id']}/messages",
            json={"content": "Bonjour !"},
            headers=auth_header(token),
        )
        assert r.status_code in (200, 201)
        msg = r.json()
        assert msg["content"] == "Bonjour !"
        assert msg["role"] == "user"

    def test_get_messages(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        conv = client.post(
            "/api/chat/conversations", json={"title": "Test"}, headers=auth_header(token)
        ).json()

        client.post(
            f"/api/chat/conversations/{conv['id']}/messages",
            json={"content": "Message 1"},
            headers=auth_header(token),
        )
        client.post(
            f"/api/chat/conversations/{conv['id']}/messages",
            json={"content": "Message 2"},
            headers=auth_header(token),
        )

        r = client.get(f"/api/chat/conversations/{conv['id']}/messages", headers=auth_header(token))
        assert r.status_code in (200, 201)
        assert len(r.json()) == 2

    def test_delete_conversation(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        conv = client.post(
            "/api/chat/conversations", json={"title": "A supprimer"}, headers=auth_header(token)
        ).json()

        r = client.delete(f"/api/chat/conversations/{conv['id']}", headers=auth_header(token))
        assert r.status_code in (200, 201)

        # Vérifier supprimée
        r = client.get(f"/api/chat/conversations/{conv['id']}", headers=auth_header(token))
        assert r.status_code == 404

    def test_conversation_not_found(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.get("/api/chat/conversations/fake-id", headers=auth_header(token))
        assert r.status_code == 404

    def test_conversations_require_auth(self, client):
        r = client.get("/api/chat/conversations")
        assert r.status_code == 401


# ============================================================
# Memory Tests (Contacts + Projects)
# ============================================================

class TestMemory:
    """Tests contacts et projets."""

    def test_create_contact(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.post(
            "/api/memory/contacts",
            json={"first_name": "Jean", "last_name": "Dupont", "email": "jean@mairie.fr"},
            headers=auth_header(token),
        )
        assert r.status_code in (200, 201)
        data = r.json()
        assert data["first_name"] == "Jean"
        assert data["email"] == "jean@mairie.fr"

    def test_list_contacts(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        client.post(
            "/api/memory/contacts",
            json={"first_name": "Alice"},
            headers=auth_header(token),
        )
        client.post(
            "/api/memory/contacts",
            json={"first_name": "Bob"},
            headers=auth_header(token),
        )

        r = client.get("/api/memory/contacts", headers=auth_header(token))
        assert r.status_code in (200, 201)
        assert len(r.json()) == 2

    def test_create_project(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.post(
            "/api/memory/projects",
            json={"name": "Refonte site mairie", "description": "Modernisation"},
            headers=auth_header(token),
        )
        assert r.status_code in (200, 201)
        assert r.json()["name"] == "Refonte site mairie"

    def test_contacts_require_auth(self, client):
        r = client.get("/api/memory/contacts")
        assert r.status_code == 401


# ============================================================
# Admin Tests
# ============================================================

class TestAdmin:
    """Tests dashboard admin."""

    def test_admin_stats(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.get("/api/admin/stats", headers=auth_header(token))
        assert r.status_code in (200, 201)
        data = r.json()
        assert "total_users" in data
        assert data["total_users"] >= 1

    def test_admin_users(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.get("/api/admin/users", headers=auth_header(token))
        assert r.status_code in (200, 201)
        assert len(r.json()) >= 1

    def test_admin_audit(self, client, seed_org_and_admin):
        _, _, token = seed_org_and_admin
        r = client.get("/api/admin/audit", headers=auth_header(token))
        assert r.status_code in (200, 201)


# ============================================================
# Multi-tenant Isolation Tests
# ============================================================

class TestMultiTenant:
    """Tests isolation multi-tenant."""

    def test_user_cannot_see_other_user_conversations(self, client, seed_org_and_admin):
        org, admin, admin_token = seed_org_and_admin

        # Créer un second user dans la même org
        import asyncio
        from app.models.database import get_session_context

        async def create_user2():
            async with get_session_context() as session:
                user2 = User(
                    email="agent@test.org",
                    hashed_password=hash_password("agent123"),
                    name="Agent Test",
                    role=UserRole.AGENT.value,
                    org_id=org.id,
                    is_active=True,
                    charter_accepted=True,
                )
                session.add(user2)
                await session.commit()
                await session.refresh(user2)
                return user2

        user2 = asyncio.get_event_loop().run_until_complete(create_user2())
        user2_token = create_access_token(user2)

        # Admin crée une conversation
        client.post(
            "/api/chat/conversations",
            json={"title": "Conv admin"},
            headers=auth_header(admin_token),
        )

        # User2 ne doit pas la voir
        r = client.get("/api/chat/conversations", headers=auth_header(user2_token))
        assert r.status_code in (200, 201)
        assert len(r.json()) == 0

    def test_user_cannot_see_other_user_contacts(self, client, seed_org_and_admin):
        org, admin, admin_token = seed_org_and_admin

        import asyncio
        from app.models.database import get_session_context

        async def create_user2():
            async with get_session_context() as session:
                user2 = User(
                    email="agent2@test.org",
                    hashed_password=hash_password("agent123"),
                    name="Agent 2",
                    role=UserRole.AGENT.value,
                    org_id=org.id,
                    is_active=True,
                    charter_accepted=True,
                )
                session.add(user2)
                await session.commit()
                await session.refresh(user2)
                return user2

        user2 = asyncio.get_event_loop().run_until_complete(create_user2())
        user2_token = create_access_token(user2)

        # Admin crée un contact
        client.post(
            "/api/memory/contacts",
            json={"first_name": "Secret"},
            headers=auth_header(admin_token),
        )

        # User2 ne doit pas le voir
        r = client.get("/api/memory/contacts", headers=auth_header(user2_token))
        assert r.status_code in (200, 201)
        assert len(r.json()) == 0


# ============================================================
# Password Hashing Tests
# ============================================================

class TestPasswordHashing:
    """Tests bcrypt."""

    def test_hash_and_verify(self):
        hashed = hash_password("motdepasse123")
        assert verify_password("motdepasse123", hashed)
        assert not verify_password("mauvais", hashed)

    def test_different_hashes(self):
        h1 = hash_password("test")
        h2 = hash_password("test")
        assert h1 != h2  # Salt différent
        assert verify_password("test", h1)
        assert verify_password("test", h2)
