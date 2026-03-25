"""
Thérèse Server - Files Router (RAG)

Endpoints pour la gestion de fichiers et l'indexation RAG.
Upload, listing, suppression, indexation et recherche sémantique.
"""

import asyncio
import hashlib
import logging
import mimetypes
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.rbac import CurrentUser
from app.auth.tenant import get_owned, scope_query, set_owner
from app.config import settings
from app.models.database import get_session
from app.models.entities import FileMetadata

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Schémas
# ============================================================


class FileMetadataResponse(BaseModel):
    """Réponse avec les métadonnées d'un fichier."""

    id: str
    name: str
    extension: str
    size: int
    mime_type: str | None = None
    content_hash: str | None = None
    chunk_count: int = 0
    scope: str = "personal"
    scope_id: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime


class SearchRequest(BaseModel):
    """Requête de recherche sémantique."""

    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    """Résultat de recherche sémantique."""

    text: str
    score: float
    file_id: str | None = None
    file_name: str | None = None
    chunk_index: int | None = None
    total_chunks: int | None = None


class SearchResponse(BaseModel):
    """Réponse de recherche sémantique."""

    query: str
    results: list[SearchResult]
    total: int


# ============================================================
# Extensions autorisées
# ============================================================

ALLOWED_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log",
    ".csv", ".tsv",
    ".pdf", ".docx", ".doc", ".xlsx",
    ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".xml",
    ".html", ".css",
}

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 Mo


# ============================================================
# Helpers
# ============================================================


def _extract_text_simple(file_path: Path) -> str | None:
    """
    Extraction de texte basique pour les fichiers supportés nativement.

    Pour les formats complexes (PDF, DOCX, XLSX), tente d'utiliser
    le file_parser existant. En cas d'échec, retourne un message
    indicatif.
    """
    ext = file_path.suffix.lower()

    # Fichiers texte : lecture directe
    text_exts = {
        ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
        ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml",
        ".xml", ".html", ".css",
    }
    if ext in text_exts:
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return None

    # Formats complexes : tenter le file_parser existant
    try:
        from app.services.file_parser import extract_text
        return extract_text(file_path)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Erreur extraction texte %s : %s", file_path, e)

    # Fallback
    if ext == ".pdf":
        return "[Extraction PDF non disponible - installez pypdf]"
    if ext in {".docx", ".doc"}:
        return "[Extraction DOCX non disponible - installez python-docx]"
    if ext == ".xlsx":
        return "[Extraction XLSX non disponible - installez openpyxl]"

    return None


def _build_response(fm: FileMetadata) -> FileMetadataResponse:
    """Construit la réponse depuis un FileMetadata."""
    return FileMetadataResponse(
        id=fm.id,
        name=fm.name,
        extension=fm.extension,
        size=fm.size,
        mime_type=fm.mime_type,
        content_hash=fm.content_hash,
        chunk_count=fm.chunk_count,
        scope=fm.scope,
        scope_id=fm.scope_id,
        indexed_at=fm.indexed_at,
        created_at=fm.created_at,
    )


# ============================================================
# Endpoints
# ============================================================


@router.post("/upload", response_model=FileMetadataResponse)
async def upload_file(
    file: UploadFile,
    current_user: CurrentUser,
    scope: str = Form(default="personal"),
    scope_id: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload un fichier.

    Le fichier est sauvegardé dans {data_dir}/uploads/{org_id}/{user_id}/
    et ses métadonnées sont enregistrées en base.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    # Valider l'extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Extension {ext} non supportée. "
                f"Extensions autorisées : {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Lire le contenu pour vérifier la taille
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Le fichier dépasse la limite de 50 Mo",
        )

    # Répertoire de stockage : {data_dir}/uploads/{org_id}/{user_id}/
    org_id = current_user.org_id or "default"
    user_id = current_user.id
    upload_dir = settings.data_dir / "uploads" / org_id / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Sauvegarder le fichier
    dest_path = upload_dir / file.filename

    # Si le fichier existe déjà, ajouter un suffixe
    counter = 1
    original_stem = dest_path.stem
    while dest_path.exists():
        dest_path = upload_dir / f"{original_stem}_{counter}{ext}"
        counter += 1

    dest_path.write_bytes(content)

    # Calculer le hash et le type MIME
    content_hash = hashlib.sha256(content).hexdigest()
    mime_type, _ = mimetypes.guess_type(str(dest_path))

    # Créer l'entrée FileMetadata
    file_meta = FileMetadata(
        path=str(dest_path),
        name=dest_path.name,
        extension=ext,
        size=len(content),
        mime_type=mime_type,
        content_hash=content_hash,
        scope=scope,
        scope_id=scope_id,
    )
    set_owner(file_meta, current_user)
    session.add(file_meta)
    await session.flush()
    await session.refresh(file_meta)

    logger.info(
        "Fichier uploadé : %s (%d octets) par %s",
        file_meta.name, file_meta.size, current_user.email,
    )

    return _build_response(file_meta)


@router.get("", response_model=list[FileMetadataResponse])
async def list_files(
    current_user: CurrentUser,
    scope: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """
    Liste les fichiers de l'utilisateur.

    Filtre optionnel par scope (personal, service, organization).
    """
    stmt = select(FileMetadata).order_by(FileMetadata.created_at.desc())
    stmt = scope_query(stmt, FileMetadata, current_user)

    if scope:
        stmt = stmt.where(FileMetadata.scope == scope)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    files = result.scalars().all()

    return [_build_response(f) for f in files]


@router.get("/{file_id}", response_model=FileMetadataResponse)
async def get_file(
    file_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """Récupère les métadonnées d'un fichier."""
    file_meta = await get_owned(session, FileMetadata, file_id, current_user)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    return _build_response(file_meta)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Supprime un fichier (métadonnées + fichier physique).

    Supprime également les chunks indexés dans Qdrant si disponible.
    """
    file_meta = await get_owned(session, FileMetadata, file_id, current_user)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Supprimer les chunks Qdrant si disponible
    qdrant_cleaned = False
    try:
        from app.services.rag import get_rag_service
        rag = get_rag_service()
        status = rag.is_available()
        if status["ready"]:
            await asyncio.to_thread(rag.delete_file_chunks, file_id)
            qdrant_cleaned = True
    except Exception as e:
        logger.warning("Impossible de supprimer les chunks Qdrant : %s", e)

    # Supprimer le fichier physique
    file_path = Path(file_meta.path)
    if file_path.exists():
        try:
            file_path.unlink()
            logger.info("Fichier physique supprimé : %s", file_path)
        except OSError as e:
            logger.warning("Impossible de supprimer le fichier physique : %s", e)

    # Supprimer l'entrée en base
    await session.delete(file_meta)

    return {
        "deleted": True,
        "id": file_id,
        "qdrant_cleaned": qdrant_cleaned,
    }


@router.post("/{file_id}/index")
async def index_file(
    file_id: str,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Indexe un fichier pour la recherche RAG.

    Extrait le texte, le découpe en chunks et stocke les embeddings
    dans Qdrant (si disponible).
    """
    file_meta = await get_owned(session, FileMetadata, file_id, current_user)
    if not file_meta:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    # Vérifier la disponibilité du service RAG
    try:
        from app.services.rag import chunk_text, get_rag_service
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Service RAG non disponible",
        )

    rag = get_rag_service()
    status = rag.is_available()

    if not status["ready"]:
        missing = []
        if not status["qdrant"]:
            missing.append("qdrant-client")
        if not status["embeddings"]:
            missing.append("sentence-transformers")
        return {
            "id": file_id,
            "indexed": False,
            "message": (
                f"Dépendances manquantes : {', '.join(missing)}. "
                "Indexation non disponible en mode développement."
            ),
            "dependencies": status,
        }

    # Vérifier que le fichier existe sur le disque
    file_path = Path(file_meta.path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Le fichier n'existe plus sur le disque",
        )

    # Extraire le texte
    text_content = _extract_text_simple(file_path)
    if not text_content or text_content.startswith("["):
        # Le texte commence par [ = message de fallback (lib manquante)
        return {
            "id": file_id,
            "indexed": False,
            "message": text_content or "Impossible d'extraire le texte de ce fichier",
            "chunk_count": 0,
        }

    # Chunker le texte
    chunks = chunk_text(
        text_content,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
    )

    if not chunks:
        return {
            "id": file_id,
            "indexed": False,
            "message": "Aucun contenu textuel à indexer",
            "chunk_count": 0,
        }

    # Supprimer les anciens chunks si ré-indexation
    if file_meta.chunk_count > 0:
        try:
            await asyncio.to_thread(rag.delete_file_chunks, file_id)
        except Exception as e:
            logger.warning("Erreur suppression anciens chunks : %s", e)

    # Indexer dans Qdrant
    org_id = current_user.org_id or "default"
    try:
        count = await asyncio.to_thread(
            rag.index_chunks,
            file_id,
            org_id,
            chunks,
            file_meta.name,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Erreur indexation fichier %s : %s", file_id, e)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de l'indexation du fichier",
        )

    # Mettre à jour les métadonnées
    file_meta.chunk_count = count
    file_meta.indexed_at = datetime.utcnow()
    file_meta.updated_at = datetime.utcnow()
    session.add(file_meta)

    logger.info(
        "Fichier indexé : %s (%d chunks) par %s",
        file_meta.name, count, current_user.email,
    )

    return {
        "id": file_id,
        "indexed": True,
        "chunk_count": count,
        "file_name": file_meta.name,
        "indexed_at": file_meta.indexed_at.isoformat(),
    }


@router.post("/search", response_model=SearchResponse)
async def search_files(
    request: SearchRequest,
    current_user: CurrentUser,
    session: AsyncSession = Depends(get_session),
):
    """
    Recherche sémantique dans les documents indexés.

    Interroge Qdrant pour trouver les chunks les plus pertinents
    par rapport à la requête, filtrés par organisation.
    """
    # Vérifier la disponibilité du service RAG
    try:
        from app.services.rag import get_rag_service
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Service RAG non disponible",
        )

    rag = get_rag_service()
    status = rag.is_available()

    if not status["ready"]:
        missing = []
        if not status["qdrant"]:
            missing.append("qdrant-client")
        if not status["embeddings"]:
            missing.append("sentence-transformers")
        raise HTTPException(
            status_code=503,
            detail=(
                "Recherche sémantique non disponible. "
                f"Dépendances manquantes : {', '.join(missing)}"
            ),
        )

    org_id = current_user.org_id or "default"

    try:
        results = await asyncio.to_thread(
            rag.search,
            request.query,
            org_id,
            request.limit,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Erreur recherche RAG : %s", e)
        raise HTTPException(
            status_code=500,
            detail="Erreur lors de la recherche",
        )

    search_results = [
        SearchResult(
            text=r["text"],
            score=r["score"],
            file_id=r.get("file_id"),
            file_name=r.get("file_name"),
            chunk_index=r.get("chunk_index"),
            total_chunks=r.get("total_chunks"),
        )
        for r in results
    ]

    return SearchResponse(
        query=request.query,
        results=search_results,
        total=len(search_results),
    )
