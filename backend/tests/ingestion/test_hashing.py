"""H: SHA-256 hashing consistency."""

from app.ingestion.hashing import document_id_from_hash, sha256_bytes


def test_sha256_is_deterministic() -> None:
    data = b"the same bytes twice"
    assert sha256_bytes(data) == sha256_bytes(data)


def test_sha256_differs_for_different_content() -> None:
    assert sha256_bytes(b"a") != sha256_bytes(b"b")


def test_sha256_matches_known_vector() -> None:
    # SHA-256("") is a well-known constant.
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_document_id_is_derived_from_hash() -> None:
    file_hash = sha256_bytes(b"study notes content")
    assert document_id_from_hash(file_hash) == file_hash
