"""
Thérèse Server - Services

Services importés à la demande pour éviter les dépendances lourdes au démarrage.
"""

# Qdrant init/close (chargés à la demande dans main.py lifespan)
async def init_qdrant():
    from app.services.qdrant import init_qdrant as _init
    await _init()

async def close_qdrant():
    from app.services.qdrant import close_qdrant as _close
    await _close()
