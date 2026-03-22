"""Codebase Context Engine — tree-sitter parsing, embeddings, and semantic search."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .vector_store import VectorStore

logger = logging.getLogger(__name__)

# Supported source file extensions
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".go", ".java", ".rs", ".rb", ".php", ".cs"
}

# Map extension → language name
_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "c_sharp",
}


@dataclass
class CodeUnit:
    """A single indexable code unit extracted from a source file."""
    file_path: str
    unit_type: str          # "function" | "class" | "method"
    name: str
    signature: str
    docstring: str
    body: str
    language: str
    embedding: Optional[List[float]] = field(default=None)


class CodebaseContextEngine:
    """
    Indexes a Git repository using tree-sitter parsing and AWS Titan embeddings,
    then supports semantic and keyword-based code search.
    """

    def __init__(self, repo_path: str, vector_store: "VectorStore") -> None:
        self.repo_path = Path(repo_path)
        self.vector_store = vector_store
        self._fallback_model = None  # lazy-initialized SentenceTransformer

        # boto3 Bedrock client for embeddings (None if unavailable)
        self._bedrock_client = None
        try:
            import boto3
            from clarity.config import settings
            session = boto3.Session(
                profile_name=settings.aws_profile_name,
                region_name=settings.aws_region_name,
            )
            self._bedrock_client = session.client("bedrock-runtime")
        except Exception as exc:
            logger.warning("Bedrock embedding client unavailable: %s", exc)

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_file(self, path: Path) -> List[CodeUnit]:
        """Parse a source file with tree-sitter and return extracted CodeUnits."""
        ext = path.suffix.lower()
        language = _EXT_TO_LANG.get(ext)
        if language is None:
            return []

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return []

        # Try tree-sitter first; fall back to regex-based extraction
        units = self._parse_with_treesitter(path, source, language)
        if units is None:
            units = self._parse_with_regex(path, source, language)
        return units

    def _parse_with_treesitter(
        self, path: Path, source: str, language: str
    ) -> Optional[List[CodeUnit]]:
        """
        Use tree-sitter to extract function/class/method nodes.
        Returns None if tree-sitter or the grammar is not installed.
        """
        try:
            import tree_sitter_languages  # type: ignore
            from tree_sitter import Language, Parser  # type: ignore
        except ImportError:
            return None

        try:
            lang = tree_sitter_languages.get_language(language)
        except Exception:
            return None

        parser = Parser()
        parser.set_language(lang)
        tree = parser.parse(source.encode("utf-8"))
        units: List[CodeUnit] = []
        source_bytes = source.encode("utf-8")

        def _text(node) -> str:
            return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def _first_string_child(node) -> str:
            """Return the text of the first string literal child (docstring)."""
            for child in node.children:
                if child.type in ("string", "expression_statement"):
                    txt = _text(child).strip().strip('"\'').strip('"""').strip("'''")
                    if txt:
                        return txt
            return ""

        def walk(node, class_name: Optional[str] = None):
            if node.type in ("function_definition", "function_declaration", "method_definition"):
                name_node = node.child_by_field_name("name")
                name = _text(name_node) if name_node else "<anonymous>"
                unit_type = "method" if class_name else "function"
                body_node = node.child_by_field_name("body")
                docstring = _first_string_child(body_node) if body_node else ""
                units.append(CodeUnit(
                    file_path=str(path),
                    unit_type=unit_type,
                    name=name,
                    signature=_text(node).splitlines()[0],
                    docstring=docstring,
                    body=_text(node),
                    language=language,
                ))
            elif node.type in ("class_definition", "class_declaration"):
                name_node = node.child_by_field_name("name")
                name = _text(name_node) if name_node else "<anonymous>"
                body_node = node.child_by_field_name("body")
                docstring = _first_string_child(body_node) if body_node else ""
                units.append(CodeUnit(
                    file_path=str(path),
                    unit_type="class",
                    name=name,
                    signature=_text(node).splitlines()[0],
                    docstring=docstring,
                    body=_text(node),
                    language=language,
                ))
                # Walk children with class context
                for child in node.children:
                    walk(child, class_name=name)
                return  # already walked children

            for child in node.children:
                walk(child, class_name=class_name)

        walk(tree.root_node)
        return units

    def _parse_with_regex(
        self, path: Path, source: str, language: str
    ) -> List[CodeUnit]:
        """Regex-based fallback parser for Python and JS/TS."""
        units: List[CodeUnit] = []
        if language == "python":
            # Match top-level and class-level defs
            pattern = re.compile(
                r'^(class|def)\s+(\w+)\s*(\([^)]*\))?[^:]*:',
                re.MULTILINE,
            )
            for m in pattern.finditer(source):
                kind = "class" if m.group(1) == "class" else "function"
                units.append(CodeUnit(
                    file_path=str(path),
                    unit_type=kind,
                    name=m.group(2),
                    signature=m.group(0),
                    docstring="",
                    body=m.group(0),
                    language=language,
                ))
        elif language in ("javascript", "typescript"):
            pattern = re.compile(
                r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()',
                re.MULTILINE,
            )
            for m in pattern.finditer(source):
                name = m.group(1) or m.group(2) or "<anonymous>"
                units.append(CodeUnit(
                    file_path=str(path),
                    unit_type="function",
                    name=name,
                    signature=m.group(0),
                    docstring="",
                    body=m.group(0),
                    language=language,
                ))
        return units

    # ── Embedding ────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> Optional[List[float]]:
        """
        Generate a vector embedding for *text*.

        Primary: AWS Titan Embeddings via Bedrock.
        Fallback: sentence-transformers (lazy-initialized).
        Returns None if both fail.
        """
        if self._bedrock_client is not None:
            try:
                import json as _json
                body = _json.dumps({"inputText": text[:8192]})
                response = self._bedrock_client.invoke_model(
                    body=body,
                    modelId="amazon.titan-embed-text-v1",
                    accept="application/json",
                    contentType="application/json",
                )
                result = _json.loads(response["body"].read())
                return result.get("embedding")
            except Exception as exc:
                logger.warning("Bedrock embedding failed, trying fallback: %s", exc)

        # Sentence-transformers fallback
        try:
            if self._fallback_model is None:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._fallback_model = SentenceTransformer("all-MiniLM-L6-v2")
            vector = self._fallback_model.encode(text, show_progress_bar=False)
            return vector.tolist()
        except Exception as exc:
            logger.warning("Sentence-transformer embedding failed: %s", exc)
            return None

    # ── Public API ───────────────────────────────────────────────────────────

    async def index_repository(self) -> int:
        """
        Walk repo_path, parse every supported source file, embed each CodeUnit,
        and store it in the vector store.  Returns the total count indexed.
        """
        count = 0
        for path in self.repo_path.rglob("*"):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if any(part.startswith(".") for part in path.parts):
                continue  # skip hidden dirs (e.g. .git)
            units = self._parse_file(path)
            for unit in units:
                unit.embedding = self._embed(f"{unit.signature}\n{unit.docstring}\n{unit.body}")
                await self.vector_store.add(unit)
                count += 1
        logger.info("Indexed %d code units from %s", count, self.repo_path)
        return count

    async def search(self, query: str, top_k: int = 5) -> List[CodeUnit]:
        """
        Semantic search: embed query → vector store search.
        Falls back to keyword search if embedding or vector store fails.
        """
        try:
            embedding = self._embed(query)
            if embedding is not None:
                return await self.vector_store.search(embedding, top_k)
        except Exception as exc:
            logger.warning("Vector search failed, falling back to keyword: %s", exc)

        return self.vector_store.search_by_keyword(query, top_k)

    def store_gotcha(self, pattern: str, description: str) -> None:
        """Append a known anti-pattern entry to gotchas.jsonl."""
        gotchas_path = self.repo_path / "gotchas.jsonl"
        entry = {"pattern": pattern, "description": description}
        with gotchas_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
        logger.info("Stored gotcha: %s", pattern)
