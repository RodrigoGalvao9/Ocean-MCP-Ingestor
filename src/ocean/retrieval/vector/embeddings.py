"""Embeddings: denso (Cloudflare Workers AI) e esparso (BM25 local, fastembed)."""

import unicodedata
from functools import lru_cache

from ocean.shared.config import get_settings
from ocean.shared.http import build_client, request

SPARSE_MODEL = "Qdrant/bm25"
SPARSE_LANGUAGE = "portuguese"


@lru_cache(maxsize=1)
def _sparse_model():
    from fastembed import SparseTextEmbedding  # import tardio: pesado e só usado aqui

    cache_dir = get_settings().fastembed_cache_dir
    try:
        return SparseTextEmbedding(
            model_name=SPARSE_MODEL, cache_dir=cache_dir, language=SPARSE_LANGUAGE
        )
    except (TypeError, ValueError):
        return SparseTextEmbedding(model_name=SPARSE_MODEL, cache_dir=cache_dir)


def embed(texts: list[str]) -> list[list[float]]:
    """Embeddings densos gerados remotamente pela Cloudflare."""
    if not texts:
        return []
    settings = get_settings()
    url = settings.cloudflare_embedding_url
    if not url or not settings.cloudflare_api_token:
        raise RuntimeError("CLOUDFLARE_ACCOUNT_ID e CLOUDFLARE_API_TOKEN precisam estar definidos")

    with build_client(timeout=60.0) as client:
        response = request(
            client,
            "POST",
            url,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
            json={"input": texts, "dimensions": settings.embedding_dim},
        )
    body = response.json()
    body = body.get("result", body)
    vectors = [item["embedding"] for item in body["data"]]

    if len(vectors) != len(texts):
        raise RuntimeError(f"Cloudflare retornou {len(vectors)} vetores para {len(texts)} textos")
    if any(len(v) != settings.embedding_dim for v in vectors):
        raise RuntimeError(f"Dimensão retornada diferente de {settings.embedding_dim}")
    return vectors


def strip_accents(text: str) -> str:
    """Normaliza acentos para melhorar a correspondência do BM25."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def embed_sparse(texts: list[str]) -> list[tuple[list[int], list[float]]]:
    plain = [strip_accents(t) for t in texts]
    return [(e.indices.tolist(), e.values.tolist()) for e in _sparse_model().embed(plain)]


def embed_sparse_query(query: str) -> tuple[list[int], list[float]]:
    e = next(iter(_sparse_model().query_embed(strip_accents(query))))
    return e.indices.tolist(), e.values.tolist()
