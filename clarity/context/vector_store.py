"""Vector store abstractions for the Codebase Context Engine."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List

from .engine import CodeUnit


class VectorStore(ABC):
    """Abstract base class for vector stores."""

    @abstractmethod
    async def add(self, unit: CodeUnit) -> None: ...

    @abstractmethod
    async def search(self, query_embedding: List[float], top_k: int) -> List[CodeUnit]: ...

    @abstractmethod
    async def count(self) -> int: ...


class InMemoryVectorStore(VectorStore):
    """In-memory vector store using cosine similarity for semantic search."""

    def __init__(self) -> None:
        self._units: List[CodeUnit] = []

    async def add(self, unit: CodeUnit) -> None:
        self._units.append(unit)

    async def search(self, query_embedding: List[float], top_k: int) -> List[CodeUnit]:
        scored: list[tuple[float, CodeUnit]] = []
        for unit in self._units:
            if unit.embedding is None:
                continue
            sim = _cosine_similarity(query_embedding, unit.embedding)
            scored.append((sim, unit))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [unit for _, unit in scored[:top_k]]

    async def count(self) -> int:
        return len(self._units)

    def search_by_keyword(self, query: str, top_k: int) -> List[CodeUnit]:
        """Keyword-based fallback search across unit name, signature, docstring, and body."""
        words = query.lower().split()
        scored: list[tuple[int, CodeUnit]] = []
        for unit in self._units:
            combined = " ".join([
                unit.name or "",
                unit.signature or "",
                unit.docstring or "",
                unit.body or "",
            ]).lower()
            score = sum(1 for word in words if word in combined)
            if score > 0:
                scored.append((score, unit))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [unit for _, unit in scored[:top_k]]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
