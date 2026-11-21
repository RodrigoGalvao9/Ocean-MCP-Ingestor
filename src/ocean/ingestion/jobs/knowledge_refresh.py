"""Indexa content/knowledge/*.md no Qdrant (denso + BM25).

Não recria a coleção: faz upsert por id estável e remove só o que saiu da pasta,
assim o servidor MCP continua respondendo durante a atualização.
"""

import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointIdsList,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from ocean.ingestion.jobs.base import JobResult
from ocean.ingestion.parsers.knowledge_md import load_directory
from ocean.retrieval.vector.embeddings import embed, embed_sparse
from ocean.retrieval.vector.retriever import DENSE, SPARSE
from ocean.shared.config import Settings

log = logging.getLogger(__name__)
_NAMESPACE = uuid.UUID("6f1c2b1e-3a55-4a0e-9a53-0c2d7a1b9e10")


def _point_id(doc_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, doc_id))


def run(settings: Settings) -> JobResult:
    docs = load_directory(settings.knowledge_dir)
    if not docs:
        raise RuntimeError(f"nenhum documento em {settings.knowledge_dir}")
    log.info("documentos lidos", extra={"count": len(docs)})

    texts = [f"{d.titulo}. {d.texto}" for d in docs]
    dense = embed(texts)
    sparse = embed_sparse(texts)

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = settings.qdrant_collection
    if not client.collection_exists(collection):
        client.create_collection(
            collection_name=collection,
            vectors_config={
                DENSE: VectorParams(size=settings.embedding_dim, distance=Distance.COSINE)
            },
            sparse_vectors_config={SPARSE: SparseVectorParams(modifier=Modifier.IDF)},
        )

    points = [
        PointStruct(
            id=_point_id(d.id),
            vector={DENSE: dv, SPARSE: SparseVector(indices=si, values=sv)},
            payload={
                "doc_id": d.id,
                "titulo": d.titulo,
                "texto": d.texto,
                "tags": d.tags,
                "fonte": d.fonte,
                "url": d.url,
                "revisado": d.revisado,
            },
        )
        for d, dv, (si, sv) in zip(docs, dense, sparse, strict=True)
    ]
    client.upsert(collection_name=collection, points=points)

    # Remove pontos de documentos que não existem mais na pasta.
    keep = {_point_id(d.id) for d in docs}
    stale: list[str] = []
    offset = None
    while True:
        found, offset = client.scroll(
            collection_name=collection, limit=100, offset=offset, with_payload=False
        )
        stale += [str(p.id) for p in found if str(p.id) not in keep]
        if offset is None:
            break
    if stale:
        client.delete(collection_name=collection, points_selector=PointIdsList(points=stale))
        log.info("documentos removidos", extra={"count": len(stale)})

    return JobResult(rows=len(points), source_version=f"{len(docs)} docs")
