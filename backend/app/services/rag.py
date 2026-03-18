"""
Thérèse Server - Service RAG (Retrieval-Augmented Generation)

Service léger pour le chunking de texte, l'indexation et la recherche
sémantique via Qdrant. Gère gracieusement les dépendances manquantes
(sentence-transformers, qdrant-client).
"""

import logging
from typing import Any
from uuid import uuid4

from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# Détection des dépendances lourdes
# ============================================================

HAS_QDRANT = False
HAS_EMBEDDINGS = False

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )
    HAS_QDRANT = True
except ImportError:
    logger.info("qdrant-client non disponible - indexation et recherche RAG désactivées")

try:
    from sentence_transformers import SentenceTransformer
    HAS_EMBEDDINGS = True
except ImportError:
    logger.info("sentence-transformers non disponible - embeddings désactivés")


# ============================================================
# Chunking
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """
    Découpe un texte en chunks avec chevauchement.

    Essaie de couper sur les paragraphes (double saut de ligne),
    puis sur les sauts de ligne simples, puis en fin de phrase.

    Args:
        text: Texte source à découper.
        chunk_size: Taille cible de chaque chunk (en caractères).
        overlap: Nombre de caractères de chevauchement entre chunks.

    Returns:
        Liste de chunks de texte.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        # Chercher un point de coupure naturel
        segment = text[start:end]
        cut_point = end

        # Priorité 1 : double saut de ligne (paragraphe)
        para_idx = segment.rfind("\n\n")
        if para_idx > chunk_size // 4:
            cut_point = start + para_idx + 2
        else:
            # Priorité 2 : saut de ligne simple
            line_idx = segment.rfind("\n")
            if line_idx > chunk_size // 4:
                cut_point = start + line_idx + 1
            else:
                # Priorité 3 : fin de phrase
                for sep in (". ", "! ", "? "):
                    sent_idx = segment.rfind(sep)
                    if sent_idx > chunk_size // 4:
                        cut_point = start + sent_idx + len(sep)
                        break

        chunk = text[start:cut_point].strip()
        if chunk:
            chunks.append(chunk)

        start = max(cut_point - overlap, start + 1)

    return chunks


# ============================================================
# Service RAG
# ============================================================

class RAGService:
    """
    Service RAG pour indexation et recherche sémantique de documents.

    Fonctionne en mode dégradé si Qdrant ou sentence-transformers
    ne sont pas installés.
    """

    COLLECTION_NAME = "therese-files"

    def __init__(self) -> None:
        self._client: Any | None = None
        self._model: Any | None = None

    # ----------------------------------------------------------
    # Initialisation paresseuse
    # ----------------------------------------------------------

    def _get_client(self) -> Any:
        """Obtient ou crée le client Qdrant."""
        if not HAS_QDRANT:
            raise RuntimeError(
                "qdrant-client non installé. "
                "Installez-le avec : pip install qdrant-client"
            )

        if self._client is None:
            qdrant_url = settings.qdrant_url
            logger.info("Connexion Qdrant : %s", qdrant_url)
            self._client = QdrantClient(url=qdrant_url, timeout=10)
            self._ensure_collection()

        return self._client

    def _get_model(self) -> Any:
        """Obtient ou crée le modèle d'embeddings."""
        if not HAS_EMBEDDINGS:
            raise RuntimeError(
                "sentence-transformers non installé. "
                "Installez-le avec : pip install sentence-transformers"
            )

        if self._model is None:
            model_name = settings.embedding_model
            logger.info("Chargement modèle embeddings : %s", model_name)
            self._model = SentenceTransformer(
                model_name,
                trust_remote_code=True,
                device="cpu",
            )
            logger.info("Modèle embeddings chargé")

        return self._model

    def _ensure_collection(self) -> None:
        """Crée la collection Qdrant si elle n'existe pas."""
        client = self._client
        if client is None:
            return

        collections = client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)

        if not exists:
            logger.info("Création collection Qdrant : %s", self.COLLECTION_NAME)
            client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection %s créée", self.COLLECTION_NAME)

    def _embed(self, text: str) -> list[float]:
        """Génère un embedding pour un texte."""
        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Génère des embeddings pour plusieurs textes."""
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    # ----------------------------------------------------------
    # Vérification de disponibilité
    # ----------------------------------------------------------

    @staticmethod
    def is_available() -> dict[str, bool]:
        """Vérifie la disponibilité des dépendances."""
        return {
            "qdrant": HAS_QDRANT,
            "embeddings": HAS_EMBEDDINGS,
            "ready": HAS_QDRANT and HAS_EMBEDDINGS,
        }

    # ----------------------------------------------------------
    # Indexation
    # ----------------------------------------------------------

    def index_chunks(
        self,
        file_id: str,
        org_id: str,
        chunks: list[str],
        file_name: str | None = None,
    ) -> int:
        """
        Indexe des chunks de texte dans Qdrant.

        Args:
            file_id: ID du fichier source.
            org_id: ID de l'organisation (isolation multi-tenant).
            chunks: Liste de chunks de texte à indexer.
            file_name: Nom du fichier (métadonnée optionnelle).

        Returns:
            Nombre de chunks indexés.

        Raises:
            RuntimeError: Si Qdrant ou sentence-transformers non disponible.
        """
        if not chunks:
            return 0

        client = self._get_client()
        embeddings = self._embed_batch(chunks)

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            point_id = str(uuid4())
            payload = {
                "text": chunk,
                "file_id": file_id,
                "org_id": org_id,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            if file_name:
                payload["file_name"] = file_name

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points,
        )

        logger.info(
            "Indexé %d chunks pour le fichier %s (org=%s)",
            len(points), file_id, org_id,
        )
        return len(points)

    # ----------------------------------------------------------
    # Recherche
    # ----------------------------------------------------------

    def search(
        self,
        query: str,
        org_id: str,
        limit: int = 5,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Recherche sémantique dans les documents indexés.

        Args:
            query: Requête de recherche en langage naturel.
            org_id: ID de l'organisation (isolation multi-tenant).
            limit: Nombre maximum de résultats.
            score_threshold: Score minimum de pertinence.

        Returns:
            Liste de résultats avec texte, score et métadonnées.

        Raises:
            RuntimeError: Si Qdrant ou sentence-transformers non disponible.
        """
        client = self._get_client()
        query_embedding = self._embed(query)

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="org_id",
                    match=MatchValue(value=org_id),
                ),
            ]
        )

        results = client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold,
        ).points

        return [
            {
                "text": hit.payload.get("text", "") if hit.payload else "",
                "score": round(hit.score, 4),
                "file_id": hit.payload.get("file_id") if hit.payload else None,
                "file_name": hit.payload.get("file_name") if hit.payload else None,
                "chunk_index": hit.payload.get("chunk_index") if hit.payload else None,
                "total_chunks": hit.payload.get("total_chunks") if hit.payload else None,
            }
            for hit in results
        ]

    # ----------------------------------------------------------
    # Suppression
    # ----------------------------------------------------------

    def delete_file_chunks(self, file_id: str) -> None:
        """
        Supprime tous les chunks d'un fichier dans Qdrant.

        Args:
            file_id: ID du fichier dont supprimer les chunks.
        """
        client = self._get_client()

        scroll_result = client.scroll(
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="file_id",
                        match=MatchValue(value=file_id),
                    ),
                ]
            ),
            limit=10000,
        )[0]

        if not scroll_result:
            logger.debug("Aucun chunk trouvé pour le fichier %s", file_id)
            return

        point_ids = [str(p.id) for p in scroll_result]
        client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=point_ids,
        )

        logger.info(
            "Supprimé %d chunks pour le fichier %s",
            len(point_ids), file_id,
        )


# ============================================================
# Instance singleton
# ============================================================

_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Obtient l'instance singleton du service RAG."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
