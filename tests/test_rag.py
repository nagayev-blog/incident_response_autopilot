"""
Tests for the RAG ingestion and retrieval layer.

All tests use an in-memory (temp-dir) ChromaDB so they never pollute or depend
on the real ./data/chroma_db persistence store.
"""

import pathlib
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collection(tmp_path: pathlib.Path) -> Any:
    """Create a fresh in-memory Chroma collection backed by a temp dir."""
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

    client = chromadb.PersistentClient(path=str(tmp_path))
    ef = DefaultEmbeddingFunction()
    return client.get_or_create_collection(
        name="test_kb",
        embedding_function=ef,  # type: ignore[arg-type]
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# ingestion.py
# ---------------------------------------------------------------------------

class TestIngestion:
    def test_get_chroma_client_singleton(self, tmp_path: pathlib.Path) -> None:
        """get_chroma_client returns the same instance on repeated calls."""
        import src.rag.ingestion as ing

        # Reset module-level singleton before test
        ing._client = None
        with patch("src.rag.ingestion.settings") as mock_cfg:
            mock_cfg.chroma_db_path = str(tmp_path)
            mock_cfg.chroma_collection_name = "test-kb"
            mock_cfg.rag_min_chunk_len = 10

            c1 = ing.get_chroma_client()
            c2 = ing.get_chroma_client()
            assert c1 is c2
            ing._client = None  # reset after test

    def test_ingest_is_idempotent(self, tmp_path: pathlib.Path) -> None:
        """Running get_or_ingest_collection twice does not duplicate chunks."""
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        import src.rag.ingestion as ing

        client = chromadb.PersistentClient(path=str(tmp_path))

        with patch("src.rag.ingestion.settings") as mock_cfg:
            mock_cfg.chroma_collection_name = "test-kb"
            mock_cfg.rag_min_chunk_len = 10

            col1 = ing.get_or_ingest_collection(client)
            count_after_first = col1.count()

            col2 = ing.get_or_ingest_collection(client)
            count_after_second = col2.count()

        assert count_after_first == count_after_second, (
            "Second ingestion call must not add duplicate chunks"
        )
        assert count_after_first > 0, "At least some chunks must be indexed"

    def test_short_chunks_are_filtered(self, tmp_path: pathlib.Path) -> None:
        """Chunks shorter than rag_min_chunk_len must be dropped."""
        import chromadb
        import src.rag.ingestion as ing

        # Create a synthetic md file with one long and one very short chunk
        kb_dir = tmp_path / "knowledge_base" / "runbooks"
        kb_dir.mkdir(parents=True)
        (kb_dir / "rb_test.md").write_text(
            "# Test Runbook\n\nThis is a long enough chunk with real content about incidents.\n\nok",
            encoding="utf-8",
        )

        client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))

        with patch("src.rag.ingestion.settings") as mock_cfg, \
             patch("src.rag.ingestion._KNOWLEDGE_BASE_ROOT", tmp_path / "knowledge_base"):
            mock_cfg.chroma_collection_name = "test-kb-filter"
            mock_cfg.rag_min_chunk_len = 20  # "ok" (2 chars) must be dropped

            col = ing.get_or_ingest_collection(client)

        # "ok" is only 2 characters — must not appear in any indexed document
        results = col.get()
        assert all("ok" != doc.strip() for doc in results["documents"] or [])


# ---------------------------------------------------------------------------
# retriever.py
# ---------------------------------------------------------------------------

class TestRetriever:
    def _patched_retrieve(
        self,
        alert: dict[str, Any],
        collection: Any,
        severity: str = "HIGH",
        incident_type: str = "availability",
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Call retrieve_similar with a mocked collection to avoid real ChromaDB path."""
        from src.rag import retriever

        with patch.object(retriever, "get_chroma_client"), \
             patch.object(retriever, "get_or_ingest_collection", return_value=collection):
            return retriever.retrieve_similar(
                alert=alert,
                severity=severity,
                incident_type=incident_type,
                top_k=top_k,
            )

    def test_returns_list_of_dicts_with_required_keys(self, tmp_path: pathlib.Path) -> None:
        col = _make_collection(tmp_path)
        col.add(
            documents=["PostgreSQL connection pool exhausted. Scale replicas."],
            metadatas=[{"source_type": "runbook", "filename": "rb_db.md", "title": "DB Runbook"}],
            ids=["chunk-001"],
        )
        alert = {"commonAnnotations": {"summary": "DB pool exhausted"}, "commonLabels": {}}
        results = self._patched_retrieve(alert, col, top_k=1)

        assert len(results) == 1
        r = results[0]
        assert set(r.keys()) >= {"id", "title", "score", "source_type", "resolution"}

    def test_score_is_in_zero_one_range(self, tmp_path: pathlib.Path) -> None:
        col = _make_collection(tmp_path)
        col.add(
            documents=["Kafka consumer lag detected. Reset offset to fix."],
            metadatas=[{"source_type": "runbook", "filename": "rb_kafka.md", "title": "Kafka"}],
            ids=["chunk-002"],
        )
        alert = {"message": "Kafka lag too high"}
        results = self._patched_retrieve(alert, col, top_k=1)

        assert results, "Expected at least one result"
        assert 0.0 <= results[0]["score"] <= 1.0

    def test_empty_query_returns_empty_list(self, tmp_path: pathlib.Path) -> None:
        col = _make_collection(tmp_path)
        col.add(
            documents=["Some document content here that is long enough."],
            metadatas=[{"source_type": "postmortem", "filename": "pm.md", "title": "PM"}],
            ids=["chunk-003"],
        )
        # Alert with no extractable text
        alert: dict[str, Any] = {}
        results = self._patched_retrieve(alert, col, top_k=3)
        assert results == []

    def test_empty_collection_returns_empty_list(self, tmp_path: pathlib.Path) -> None:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        client = chromadb.PersistentClient(path=str(tmp_path))
        ef = DefaultEmbeddingFunction()
        empty_col = client.get_or_create_collection(
            "empty_test",
            embedding_function=ef,  # type: ignore[arg-type]
            metadata={"hnsw:space": "cosine"},
        )
        alert = {"message": "Something is broken"}
        results = self._patched_retrieve(alert, empty_col, top_k=5)
        assert results == []

    def test_resolution_max_300_chars(self, tmp_path: pathlib.Path) -> None:
        col = _make_collection(tmp_path)
        long_text = "A" * 500
        col.add(
            documents=[long_text],
            metadatas=[{"source_type": "runbook", "filename": "rb_long.md", "title": "Long"}],
            ids=["chunk-004"],
        )
        alert = {"message": "A" * 50}
        results = self._patched_retrieve(alert, col, top_k=1)

        assert results
        assert len(results[0]["resolution"]) <= 300

    def test_top_k_limits_results(self, tmp_path: pathlib.Path) -> None:
        col = _make_collection(tmp_path)
        for i in range(10):
            col.add(
                documents=[f"Incident document number {i} describing a system failure event."],
                metadatas=[{"source_type": "postmortem", "filename": f"pm_{i}.md", "title": f"PM {i}"}],
                ids=[f"chunk-{i:03d}"],
            )
        alert = {"message": "system failure"}
        results = self._patched_retrieve(alert, col, top_k=3)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# history_agent.py
# ---------------------------------------------------------------------------

class TestHistoryNode:
    def test_history_node_returns_correct_keys(self) -> None:
        from src.agents.history_agent import history_node
        from src.graph.state import IncidentState

        mock_results = [
            {
                "id": "rb_db.md",
                "title": "DB Runbook",
                "score": 0.85,
                "source_type": "runbook",
                "resolution": "Scale read replicas.",
            }
        ]
        state = IncidentState(
            alert={"message": "DB pool exhausted"},
            severity="CRITICAL",
            incident_type="availability",
        )

        with patch("src.agents.history_agent.retrieve_similar", return_value=mock_results):
            result = history_node(state)

        assert "similar_incidents" in result
        assert "metrics" in result
        assert "history" in result["metrics"]
        assert "latency_s" in result["metrics"]["history"]
        assert result["similar_incidents"] == mock_results

    def test_history_node_passes_state_fields_to_retriever(self) -> None:
        from src.agents.history_agent import history_node
        from src.graph.state import IncidentState

        state = IncidentState(
            alert={"commonAnnotations": {"summary": "OOMKilled"}},
            severity="HIGH",
            incident_type="availability",
        )

        with patch("src.agents.history_agent.retrieve_similar", return_value=[]) as mock_fn:
            history_node(state)

        mock_fn.assert_called_once_with(
            alert=state["alert"],
            severity="HIGH",
            incident_type="availability",
        )
