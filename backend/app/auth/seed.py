"""
Thérèse Server - Seed Script

Crée l'organisation par défaut et le premier administrateur.
Usage : python -m app.auth.seed
"""

import asyncio
import sys

from app.auth.backend import hash_password
from app.auth.models import Organization, User, UserRole
from app.models.database import init_db, get_session_context


async def seed():
    """Create default organization and admin user."""
    await init_db()

    async with get_session_context() as session:
        from sqlmodel import select

        # Vérifier si une org existe déjà
        stmt = select(Organization)
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            print("Base déjà initialisée (organisation existante)")
            return

        # Créer l'organisation par défaut
        org = Organization(
            name="Organisation par défaut",
            slug="default",
            max_users=100,
        )
        session.add(org)
        await session.flush()

        # Créer l'administrateur
        admin = User(
            email="admin@therese.local",
            hashed_password=hash_password("admin"),
            name="Administrateur",
            role=UserRole.ADMIN.value,
            org_id=org.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        print(f"Organisation créée : {org.name} (id: {org.id})")
        print(f"Admin créé : {admin.email} / admin")
        print("IMPORTANT : changez le mot de passe admin en production !")


if __name__ == "__main__":
    asyncio.run(seed())
