from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

TOKEN = re.compile(r"[a-z0-9]+")
STOP = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "are", "with",
    "that", "this", "from", "by", "as", "at", "be", "it", "if", "then", "than",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class ScoredChunk:
    chunk_id: str
    doc_id: str
    title: str
    category: str
    text: str
    score: float
    bm25: float
    vector: float


class HybridIndex:
    """BM25 + TF-IDF cosine + Reciprocal Rank Fusion + title rerank."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.docs_tokens = [tokenize(c["text"] + " " + c["title"]) for c in chunks]
        self.n = len(chunks) or 1
        self.df: Counter[str] = Counter()
        for tokens in self.docs_tokens:
            self.df.update(set(tokens))
        self.avgdl = sum(len(t) for t in self.docs_tokens) / self.n
        self.tfidf = [self._tfidf_vec(tokens) for tokens in self.docs_tokens]
        self.norms = [self._norm(v) for v in self.tfidf]

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def _tfidf_vec(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        if not tokens:
            return {}
        return {term: (count / len(tokens)) * self._idf(term) for term, count in tf.items()}

    @staticmethod
    def _norm(vec: dict[str, float]) -> float:
        return math.sqrt(sum(v * v for v in vec.values())) or 1.0

    def _bm25(self, query: list[str], doc_tokens: list[str]) -> float:
        tf = Counter(doc_tokens)
        score = 0.0
        k1, b = 1.5, 0.75
        dl = len(doc_tokens) or 1
        for term in query:
            if term not in tf:
                continue
            freq = tf[term]
            score += self._idf(term) * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / self.avgdl))
        return score

    def _cosine(self, query: list[str], idx: int) -> float:
        qv = self._tfidf_vec(query)
        qn = self._norm(qv)
        dv = self.tfidf[idx]
        dot = sum(qv[t] * dv.get(t, 0.0) for t in qv)
        return dot / (qn * self.norms[idx])

    def search(self, query: str, k: int = 5) -> list[ScoredChunk]:
        q = tokenize(query)
        if not q or not self.chunks:
            return []
        bm25_scores = [self._bm25(q, tokens) for tokens in self.docs_tokens]
        vec_scores = [self._cosine(q, i) for i in range(len(self.chunks))]
        bm25_rank = _ranks(bm25_scores)
        vec_rank = _ranks(vec_scores)
        fused: list[tuple[int, float]] = []
        for i in range(len(self.chunks)):
            rrf = 1 / (60 + bm25_rank[i]) + 1 / (60 + vec_rank[i])
            fused.append((i, rrf + _rerank_bonus(q, self.chunks[i])))
        fused.sort(key=lambda x: x[1], reverse=True)
        results: list[ScoredChunk] = []
        for i, score in fused[:k]:
            chunk = self.chunks[i]
            results.append(
                ScoredChunk(
                    chunk_id=chunk["chunk_id"],
                    doc_id=chunk["doc_id"],
                    title=chunk["title"],
                    category=chunk["category"],
                    text=chunk["text"],
                    score=round(score, 4),
                    bm25=round(bm25_scores[i], 4),
                    vector=round(vec_scores[i], 4),
                )
            )
        return results


def _ranks(scores: list[float]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranks = [0] * len(scores)
    for rank, i in enumerate(order, start=1):
        ranks[i] = rank
    return ranks


def _rerank_bonus(query: list[str], chunk: dict) -> float:
    title_tokens = set(tokenize(chunk["title"]))
    return 0.08 * len(set(query) & title_tokens)
