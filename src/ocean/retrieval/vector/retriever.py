"""Busca na base de conhecimento (Qdrant): densa, esparsa (BM25) ou híbrida (RRF, padrão).

Teste rápido:
    python -m ocean.retrieval.vector.retriever "Como leio a tábua de marés?"
"""

import argparse
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from ocean.retrieval.vector.embeddings import embed, embed_sparse_query
from ocean.shared.config import get_settings

DENSE = "dense"
SPARSE = "sparse"
MODES = ("dense", "sparse", "hybrid")
PREFETCH = 20  # candidatos que cada busca entrega para a fusão


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    s = get_settings()
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)


def search(query: str, k: int = 4, mode: str = "hybrid") -> list[dict]:
    """Retorna os k trechos mais relevantes. No modo híbrido o score vem da fusão RRF
    (baseado em posições) e não é comparável com o score do modo denso."""
    if mode not in MODES:
        raise ValueError(f"modo inválido: {mode!r} (use um de {MODES})")

    collection = get_settings().qdrant_collection
    dense = embed([query])[0] if mode in ("dense", "hybrid") else None
    indices, values = embed_sparse_query(query) if mode in ("sparse", "hybrid") else ([], [])
    sparse = SparseVector(indices=indices, values=values)
    client = _client()

    if mode == "sparse":
        if not indices:
            return []
        response = client.query_points(
            collection_name=collection, query=sparse, using=SPARSE, limit=k, with_payload=True
        )
    elif mode == "dense" or not indices:
        response = client.query_points(
            collection_name=collection, query=dense, using=DENSE, limit=k, with_payload=True
        )
    else:
        response = client.query_points(
            collection_name=collection,
            prefetch=[
                Prefetch(query=dense, using=DENSE, limit=PREFETCH),
                Prefetch(query=sparse, using=SPARSE, limit=PREFETCH),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=k,
            with_payload=True,
        )

    return [
        {
            "id": p.payload["doc_id"],
            "title": p.payload["titulo"],
            "text": p.payload["texto"],
            "source": p.payload.get("fonte"),
            "url": p.payload.get("url"),
            "score": round(p.score, 3),
        }
        for p in response.points
    ]


def list_topics() -> list[dict]:
    """Lista id e título de todos os documentos (percorre todas as páginas do Qdrant)."""
    collection = get_settings().qdrant_collection
    topics: list[dict] = []
    offset = None
    while True:
        points, offset = _client().scroll(
            collection_name=collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        topics += [{"id": p.payload["doc_id"], "title": p.payload["titulo"]} for p in points]
        if offset is None:
            break
    return sorted(topics, key=lambda t: t["id"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*")
    ap.add_argument("--mode", choices=MODES, default="hybrid")
    args = ap.parse_args()
    question = " ".join(args.question) or "o que é preamar?"
    print(f"Pergunta: {question}  (modo: {args.mode})\n")
    for pos, r in enumerate(search(question, k=10, mode=args.mode), start=1):
        print(f"{pos:>2}. [{r['score']}] {r['id']} - {r['title']}")
