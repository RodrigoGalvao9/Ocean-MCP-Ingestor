import pytest

from ocean.ingestion.parsers.knowledge_md import load_directory, parse_document
from ocean.shared.config import REPO_ROOT

DOC = """---
id: a
titulo: Título A
tags: x, y
fonte: Fonte
---
Texto.
"""


def test_parse_ok():
    d = parse_document(DOC)
    assert (d.id, d.titulo, d.tags) == ("a", "Título A", ["x", "y"])
    assert (d.texto, d.revisado) == ("Texto.", False)


@pytest.mark.parametrize(
    "raw",
    [
        "sem cabecalho",
        "---\nid: a\n---\ntexto",
        "---\nid: a\ntitulo: t\nfonte: f\n---\n",
        "---\nid: a",
    ],
)
def test_parse_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_document(raw)


def test_repository_content_is_valid():
    docs = load_directory(REPO_ROOT / "content" / "knowledge")
    assert len(docs) >= 4
    assert all(d.fonte for d in docs)
