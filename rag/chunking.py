"""Structure-aware chunking.

CONCEPT - why not split every N characters?
  A police statement is made of paragraphs, and each paragraph is one claim
  ("I was at my shop all day"). Cutting at a fixed size can split a claim in half
  or glue two unrelated claims together, and then neither retrieves well.
  So one paragraph = one chunk, and every chunk gets a stable citation id
  like "DOC-14 ¶4" that a human can check.

CONCEPT - contextual chunk header
  The paragraph "I was at my shop the whole day" means nothing on its own. We
  prepend the document title and type before embedding ("Statement of Imran
  Shaikh under Section 180 BNSS: ..."), so the vector knows WHO said it.

Every case folder (data/cases/<id>/documents) plus the closed-case archive is
chunked. The case_id on each chunk lets search stay inside one case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.store import ARCHIVE_DIR, CASES_DIR, ROOT, parse_front_matter  # noqa: F401 (ROOT re-exported)


@dataclass
class Chunk:
    chunk_id: str          # "DOC-14 ¶4" - the citation
    doc_id: str
    case_id: str
    doc_type: str
    title: str
    date: str
    persons: list[str] = field(default_factory=list)
    para: int = 0
    text: str = ""

    @property
    def embed_text(self) -> str:
        """Text used for search: header gives the paragraph its context."""
        return f"{self.title} ({self.doc_type}, {self.date}): {self.text}"


def parse_document(path: Path) -> tuple[dict, str]:
    return parse_front_matter(path.read_text(encoding="utf-8"))


def document_files() -> list[Path]:
    return sorted(CASES_DIR.glob("*/documents/*.md")) + sorted(ARCHIVE_DIR.glob("*.md"))


def chunk_document(path: Path) -> list[Chunk]:
    meta, body = parse_document(path)
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    persons = [p.strip() for p in meta.get("persons", "").split(";") if p.strip()]
    return [
        Chunk(
            chunk_id=f"{meta['doc_id']} ¶{i}",
            doc_id=meta["doc_id"],
            case_id=meta["case_id"],
            doc_type=meta.get("doc_type", ""),
            title=meta.get("title", path.stem),
            date=meta.get("date", ""),
            persons=persons,
            para=i,
            text=para,
        )
        for i, para in enumerate(paragraphs, start=1)
    ]


def load_all_chunks() -> list[Chunk]:
    """Every chunk in the station: all case files plus the closed-case archive."""
    chunks: list[Chunk] = []
    for f in document_files():
        chunks.extend(chunk_document(f))
    return chunks


def load_document(doc_id: str, case_id: str | None = None) -> dict | None:
    """Full document by id with numbered paragraphs. Prefers the given case (doc ids repeat across cases)."""
    files = document_files()
    if case_id:
        files = sorted(files, key=lambda f: f.parent.parent.name != case_id)
    for f in files:
        meta, _ = parse_document(f)
        if meta.get("doc_id") == doc_id:
            return {
                "doc_id": doc_id,
                "case_id": meta.get("case_id"),
                "title": meta.get("title"),
                "doc_type": meta.get("doc_type"),
                "date": meta.get("date"),
                "paragraphs": [{"cite": c.chunk_id, "text": c.text} for c in chunk_document(f)],
            }
    return None
