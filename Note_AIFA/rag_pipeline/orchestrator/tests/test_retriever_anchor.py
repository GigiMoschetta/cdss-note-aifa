"""
Tests for Stage A anchor-guided retrieval — page_end range filter.

Uses self-contained tmp_path ChromaDB instances (no live DB dependency).
"""


def test_chroma_metadata_page_types(tmp_path):
    """Verify page and page_end survive ChromaDB persistence as int, not str."""
    import chromadb

    client = chromadb.PersistentClient(path=str(tmp_path / "test_db"))
    coll = client.get_or_create_collection("test_nota")
    coll.upsert(
        ids=["c1"],
        documents=["text"],
        metadatas=[{"page": 3, "page_end": 4, "pdf_file": "test.pdf"}],
    )
    result = coll.get(ids=["c1"], include=["metadatas"])
    meta = result["metadatas"][0]
    assert isinstance(meta["page"], int), f"page is {type(meta['page'])}, expected int"
    assert isinstance(meta["page_end"], int), f"page_end is {type(meta['page_end'])}, expected int"


def test_multipage_chunk_found_by_page_end(tmp_path):
    """Chunk with page=3, page_end=4 should be found when anchor targets page=4."""
    import chromadb

    client = chromadb.PersistentClient(path=str(tmp_path / "test_db"))
    coll = client.get_or_create_collection("test_nota")
    coll.upsert(
        ids=["c1"],
        documents=["regulatory text spanning pages 3-4"],
        metadatas=[{"page": 3, "page_end": 4, "pdf_file": "Nota_66.pdf", "nota_id": "66", "section": ""}],
    )

    # Exact page=4 should NOT match (chunk starts at page=3)
    exact = coll.get(
        where={"$and": [{"pdf_file": {"$eq": "Nota_66.pdf"}}, {"page": {"$eq": 4}}]},
        include=["documents", "metadatas"],
    )
    assert len(exact["ids"]) == 0, "Exact page=4 should not match chunk with page=3"

    # Range filter: page <= 4 AND page_end >= 4 should find it
    range_result = coll.get(
        where={"$and": [
            {"pdf_file": {"$eq": "Nota_66.pdf"}},
            {"page": {"$lte": 4}},
            {"page_end": {"$gte": 4}},
        ]},
        include=["documents", "metadatas"],
    )
    assert len(range_result["ids"]) == 1
    assert range_result["ids"][0] == "c1"


def test_exact_page_still_preferred(tmp_path):
    """When exact page matches, range filter is not needed (fast path)."""
    import chromadb

    client = chromadb.PersistentClient(path=str(tmp_path / "test_db"))
    coll = client.get_or_create_collection("test_nota")
    coll.upsert(
        ids=["c1", "c2"],
        documents=["exact match text", "range match text"],
        metadatas=[
            {"page": 4, "page_end": 4, "pdf_file": "test.pdf", "nota_id": "66", "section": ""},
            {"page": 3, "page_end": 5, "pdf_file": "test.pdf", "nota_id": "66", "section": ""},
        ],
    )

    # Exact page=4 finds c1 directly
    exact = coll.get(
        where={"$and": [{"pdf_file": {"$eq": "test.pdf"}}, {"page": {"$eq": 4}}]},
        include=["documents", "metadatas"],
    )
    assert len(exact["ids"]) == 1
    assert exact["ids"][0] == "c1"
