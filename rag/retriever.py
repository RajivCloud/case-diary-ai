"""Hybrid retriever: dense (embeddings) + sparse (BM25) fused with Reciprocal Rank Fusion.

CONCEPT - two kinds of search
  * Dense / semantic search turns text into vectors; similar MEANING lands close
    together. "my account was hacked" finds "unauthorised access". It is weak at
    exact tokens like "8969204117" or "UTR SNBR526100338841".
  * Sparse / keyword search (BM25) scores documents by shared rare words. It nails
    exact numbers and names, but misses paraphrases.
  Police files are full of both (narratives AND identifiers), so we run both.

CONCEPT - Reciprocal Rank Fusion (RRF)
  The two searches give scores on different scales, so we can't add them.
  RRF uses only RANK: score = sum(1 / (60 + rank)). A chunk ranked high by
  either method rises; one ranked high by both rises most.

CONCEPT - metadata filtering
  Before ranking we can restrict to case_id / doc_type / person. That keeps the
  station's other cases out unless the agent asks for them.

CONCEPT - incremental indexing
  Each chunk's vector is cached by a hash of its text. When an IO adds a new case,
  only the new paragraphs are embedded; the index refreshes automatically.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
from rank_bm25 import BM25Okapi

from rag.chunking import ROOT, Chunk, document_files, load_all_chunks

INDEX_DIR = ROOT / "data" / "index"
CACHE = INDEX_DIR / "vector_cache.npz"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # small (~130 MB), fast on CPU, good English quality
RRF_K = 60

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _h(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(EMBED_MODEL)
    return _embedder


class HybridRetriever:
    def __init__(self, chunks: list[Chunk] | None = None, use_dense: bool = True):
        self.chunks = chunks if chunks is not None else load_all_chunks()
        self.bm25 = BM25Okapi([tokenize(c.embed_text) for c in self.chunks])
        self.vectors = None
        if use_dense:
            try:
                self.vectors = self._dense_vectors()
            except Exception as exc:  # no model download possible -> keyword-only, still works
                print(f"[retriever] dense search disabled ({exc}); using BM25 only")

    def _dense_vectors(self) -> np.ndarray:
        cache: dict[str, np.ndarray] = {}
        if CACHE.exists():
            with np.load(CACHE) as z:
                cache = {k: z[k] for k in z.files}
        keys = [_h(c.embed_text) for c in self.chunks]
        missing = [i for i, k in enumerate(keys) if k not in cache]
        if missing:
            new = list(_get_embedder().embed([self.chunks[i].embed_text for i in missing]))
            for i, v in zip(missing, new):
                v = np.asarray(v, dtype=np.float32)
                cache[keys[i]] = v / np.linalg.norm(v)
            INDEX_DIR.mkdir(parents=True, exist_ok=True)
            np.savez(CACHE, **cache)
        return np.stack([cache[k] for k in keys]) if keys else np.zeros((0, 384), dtype=np.float32)

    def _embed_query(self, query: str) -> np.ndarray:
        # bge models expect an instruction prefix on queries (not on documents); query_embed adds it
        q = np.array(list(_get_embedder().query_embed(query)), dtype=np.float32)[0]
        return q / np.linalg.norm(q)

    def search(self, query: str, k: int = 6, case_id: str | None = None,
               doc_type: str | None = None, person: str | None = None) -> list[dict]:
        idx = [
            i for i, c in enumerate(self.chunks)
            if (case_id is None or c.case_id == case_id)
            and (doc_type is None or c.doc_type == doc_type)
            and (person is None or any(person.lower() in p.lower() for p in c.persons)
                 or person.lower() in c.text.lower())
        ]
        if not idx:
            return []

        bm = self.bm25.get_scores(tokenize(query))
        sparse_order = sorted(idx, key=lambda i: bm[i], reverse=True)
        sparse_rank = {i: r for r, i in enumerate(sparse_order, start=1) if bm[i] > 0}

        dense_rank: dict[int, int] = {}
        if self.vectors is not None and len(self.vectors):
            sims = self.vectors[idx] @ self._embed_query(query)
            dense_rank = {idx[j]: r for r, j in enumerate(np.argsort(-sims), start=1)}

        fused = {i: sum(1.0 / (RRF_K + ranks[i]) for ranks in (sparse_rank, dense_rank) if i in ranks) for i in idx}
        top = sorted(fused, key=fused.get, reverse=True)[:k]
        return [
            {
                "cite": self.chunks[i].chunk_id, "case_id": self.chunks[i].case_id,
                "title": self.chunks[i].title, "doc_type": self.chunks[i].doc_type,
                "date": self.chunks[i].date, "text": self.chunks[i].text,
                "score": round(fused[i], 4), "dense_rank": dense_rank.get(i), "bm25_rank": sparse_rank.get(i),
            }
            for i in top
        ]


_singleton: HybridRetriever | None = None
_stamp: tuple | None = None


def _files_stamp() -> tuple:
    return tuple((str(f), f.stat().st_mtime_ns) for f in document_files())


def get_retriever() -> HybridRetriever:
    """Shared retriever; rebuilt automatically when any document is added or changed."""
    global _singleton, _stamp
    stamp = _files_stamp()
    if _singleton is None or stamp != _stamp:
        _singleton, _stamp = HybridRetriever(), stamp
    return _singleton
