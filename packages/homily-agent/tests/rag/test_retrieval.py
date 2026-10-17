"""Storage lifecycle and provenance checks with real Chroma and local vectors."""

import pytest

from homily_agent.rag import retrieval


class LocalEmbedding:
    """Tiny deterministic vectors keep storage tests independent of downloads."""

    def __call__(self, input):
        return [[1.0, float(len(text) % 7 + 1), 0.5] for text in input]


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval, "ONNXMiniLM_L6_V2", lambda **kwargs: LocalEmbedding())
    return retrieval.RetrievalService(persist_directory=str(tmp_path / "vectors"), min_similarity=-1)


def test_reset_on_fresh_service_removes_existing_corpus(service):
    service.add_documents(["old source"], ["old"])
    fresh = retrieval.RetrievalService(persist_directory=service.persist_directory)
    fresh.reset_collection()
    assert fresh.get_document_count() == 0


def test_deleted_collection_can_be_reused(service):
    service.add_documents(["old source"], ["old"])
    service.delete_collection()
    service.add_documents(["new source"], ["new"])
    assert service.get_document_count() == 1


def test_reingestion_updates_stable_ids(service):
    service.add_documents(["original"], ["same"], [{"source": "CCC", "paragraph_num": 1}])
    service.add_documents(["corrected"], ["same"], [{"source": "CCC", "paragraph_num": 1}])
    assert service.get_document_count() == 1
    assert service.retrieve("corrected")[0].content == "corrected"


def test_text_sources_with_same_basename_keep_distinct_identity(service, tmp_path):
    for directory, content in [("one", "first source"), ("two", "second source")]:
        source = tmp_path / "corpus" / directory / "notes.txt"
        source.parent.mkdir(parents=True)
        source.write_text(content)
    retrieval.load_theological_corpus(str(tmp_path / "corpus"), service)
    assert service.get_document_count() == 2
    assert {doc.source for doc in service.retrieve("source")} == {"one/notes.txt", "two/notes.txt"}


def test_missing_distances_are_not_fabricated_as_perfect_matches(service, monkeypatch):
    service._ensure_initialized()
    monkeypatch.setattr(
        type(service.collection),
        "query",
        lambda *args, **kwargs: {
            "documents": [["unsupported match"]],
            "distances": None,
            "metadatas": [[{"source": "unknown"}]],
        },
    )
    assert service.retrieve("query") == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (5, 5), (5, 7), (5, -1)])
def test_invalid_chunk_windows_fail_instead_of_hanging(size, overlap):
    # Empty input avoids a hang in the broken implementation while still
    # exercising the invalid configuration independently of source content.
    with pytest.raises(ValueError):
        retrieval._chunk_text("", size, overlap)


def test_chunking_does_not_emit_redundant_tail():
    assert retrieval._chunk_text("abcdef", 6, 2) == ["abcdef"]
    assert retrieval._chunk_text("abcdefghijk", 6, 2) == ["abcdef", "efghij", "ijk"]
