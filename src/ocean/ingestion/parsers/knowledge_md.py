"""Lê documentos de conhecimento em Markdown com cabeçalho simples:

---
id: glossario-mares
titulo: Preamar e baixa-mar
tags: glossario, mares
fonte: Nome da fonte
url: https://...            (opcional)
revisado: sim|nao           (opcional; nao = rascunho a revisar)
---
Texto do documento...
"""

from dataclasses import dataclass, field
from pathlib import Path

REQUIRED = ("id", "titulo", "fonte")


@dataclass(frozen=True)
class KnowledgeDoc:
    id: str
    titulo: str
    texto: str
    fonte: str
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    revisado: bool = False


def parse_document(raw: str, origin: str = "<texto>") -> KnowledgeDoc:
    lines = raw.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{origin}: cabeçalho '---' ausente")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError(f"{origin}: cabeçalho não fechado com '---'") from None

    meta: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"{origin}: linha de cabeçalho inválida: {line!r}")
        meta[key.strip().lower()] = value.strip()

    missing = [k for k in REQUIRED if not meta.get(k)]
    if missing:
        raise ValueError(f"{origin}: campos obrigatórios ausentes: {', '.join(missing)}")

    body = "\n".join(lines[end + 1 :]).strip()
    if not body:
        raise ValueError(f"{origin}: documento sem texto")

    return KnowledgeDoc(
        id=meta["id"],
        titulo=meta["titulo"],
        texto=body,
        fonte=meta["fonte"],
        url=meta.get("url") or None,
        tags=[t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        revisado=meta.get("revisado", "nao").lower() in ("sim", "true", "1"),
    )


def load_directory(directory: Path) -> list[KnowledgeDoc]:
    docs = [
        parse_document(p.read_text(encoding="utf-8"), origin=p.name)
        for p in sorted(directory.glob("*.md"))
    ]
    ids = [d.id for d in docs]
    duplicated = {i for i in ids if ids.count(i) > 1}
    if duplicated:
        raise ValueError(f"ids duplicados: {', '.join(sorted(duplicated))}")
    return docs
