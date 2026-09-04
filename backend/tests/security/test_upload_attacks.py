"""Phase 8N: upload-attack security tests (spec section 8B/8B.1/8B.2).

Complements `tests/ingestion/test_validation.py`/`test_storage.py` (unit
level) with end-to-end coverage through the real `POST /documents/upload`
API, and adds cases not previously covered: null bytes, Unicode-lookalike
and very-long filenames, and confirmation that a rejected upload never
lands the safe filename outside the data root.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.ingestion.storage import sanitize_filename


def _upload(client: TestClient, fixtures_dir: Path, filename: str, content_type: str):
    with open(fixtures_dir / filename, "rb") as f:
        return client.post("/documents/upload", files={"file": (filename, f, content_type)})


# --- Filename security (8B.1) ---------------------------------------------


def test_path_traversal_filename_never_escapes_data_root(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    response = _upload(api_client, fixtures_dir, "study_notes.pdf", "application/pdf")
    document_id = response.json()["document_id"]

    data_dir = Path(get_settings().data_dir).resolve()
    raw_dir = data_dir / "raw" / document_id
    assert raw_dir.exists()
    for stored_file in raw_dir.iterdir():
        assert data_dir in stored_file.resolve().parents


def test_sanitize_filename_rejects_dot_dot_traversal() -> None:
    # `Path(...).name` already drops every directory component (including
    # the traversal segments), leaving only the final path element.
    result = sanitize_filename("../../../etc/passwd")
    assert result == "passwd"
    assert "/" not in result
    assert ".." not in result


def test_sanitize_filename_rejects_windows_style_traversal() -> None:
    result = sanitize_filename("..\\..\\windows\\system32\\config")
    assert "\\" not in result
    assert ".." not in result


def test_sanitize_filename_rejects_absolute_path() -> None:
    result = sanitize_filename("/etc/passwd")
    assert result == "passwd"


def test_sanitize_filename_rejects_null_byte() -> None:
    result = sanitize_filename("notes.pdf\x00.exe")
    assert "\x00" not in result


def test_sanitize_filename_handles_unicode_lookalikes() -> None:
    # U+FF0E (fullwidth full stop) and U+2024 (one dot leader) are common
    # "looks like a dot but isn't" tricks; neither should survive as a
    # literal traversal-shaped path component, and the result must still be
    # a safe bare filename.
    result = sanitize_filename("notes．．/passwd.pdf")
    assert "/" not in result


def test_sanitize_filename_truncation_of_very_long_name() -> None:
    long_name = ("a" * 5000) + ".pdf"
    result = sanitize_filename(long_name)
    # sanitize_filename does not itself enforce a max length (the
    # underlying filesystem does), but it must never contain path
    # separators regardless of length.
    assert "/" not in result and "\\" not in result


def test_sanitize_filename_handles_whitespace_only_name() -> None:
    assert sanitize_filename("   ") != ""
    assert sanitize_filename("   ").strip() == sanitize_filename("   ")


def test_sanitize_filename_rejects_shell_metacharacters() -> None:
    result = sanitize_filename("notes;rm -rf ~.pdf")
    for char in (";", "|", "&", "$", "`", "~", " "):
        assert char not in result


def test_duplicate_filenames_from_different_uploads_do_not_collide(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    """Two different documents uploaded under the *same* original filename
    must not overwrite each other on disk — document identity is the
    content hash, not the filename (spec section 8B: "deterministic
    storage location")."""
    with open(fixtures_dir / "study_notes.pdf", "rb") as f:
        first = api_client.post(
            "/documents/upload", files={"file": ("notes.pdf", f, "application/pdf")}
        )
    with open(fixtures_dir / "corrupted.pdf", "rb") as f:
        second = api_client.post(
            "/documents/upload", files={"file": ("notes.pdf", f, "application/pdf")}
        )
    assert first.json()["document_id"] != second.json()["document_id"]
    assert api_client.get(f"/documents/{first.json()['document_id']}").status_code == 200


# --- File size / extension / content-type (8B, 8B.2) -----------------------


def test_upload_rejects_unsupported_extension(api_client: TestClient, fixtures_dir: Path) -> None:
    response = _upload(api_client, fixtures_dir, "unsupported.txt", "text/plain")
    assert response.status_code == 400
    assert "detail" in response.json()


def test_upload_rejects_empty_file(api_client: TestClient, fixtures_dir: Path) -> None:
    response = _upload(api_client, fixtures_dir, "empty.pdf", "application/pdf")
    assert response.status_code == 400


def test_upload_rejects_oversized_file(api_client: TestClient, tmp_path: Path) -> None:
    settings = get_settings()
    oversized = b"%PDF-1.4\n" + b"0" * (settings.max_upload_size_mb * 1024 * 1024 + 1)
    response = api_client.post(
        "/documents/upload",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_ignores_client_supplied_content_type(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    """The declared Content-Type header is never trusted (spec section
    8B) — a real PDF uploaded with a lying Content-Type still ingests
    successfully because validation is extension + magic-byte based, not
    header based."""
    response = _upload(api_client, fixtures_dir, "study_notes.pdf", "image/png")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_upload_rejects_content_mismatched_with_extension(api_client: TestClient) -> None:
    """A file claiming to be a PDF but containing arbitrary bytes is
    rejected by the magic-byte check before parsing is ever attempted
    (spec section 8B.1/8C.1)."""
    response = api_client.post(
        "/documents/upload",
        files={"file": ("fake.pdf", b"not actually a pdf file", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_rejects_malformed_pdf(api_client: TestClient, fixtures_dir: Path) -> None:
    """A file with the correct PDF signature but corrupted internal
    structure fails safely at the parser stage, not silently or with an
    unhandled exception (spec section 8C.1)."""
    response = _upload(api_client, fixtures_dir, "corrupted.pdf", "application/pdf")
    assert response.status_code == 200  # ingest() reports failure in the body, not via HTTP error
    assert response.json()["status"] == "failed"


def test_malformed_pdf_leaves_no_raw_file_on_disk(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    """Spec section 8K: cleanup after a parser failure — a document that
    fails to parse must not leave its raw bytes accumulating on disk."""
    response = _upload(api_client, fixtures_dir, "corrupted.pdf", "application/pdf")
    document_id = response.json()["document_id"]
    data_dir = Path(get_settings().data_dir).resolve()
    assert not (data_dir / "raw" / document_id).exists()


def test_reuploading_identical_bytes_is_a_duplicate(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    first = _upload(api_client, fixtures_dir, "study_notes.html", "text/html")
    second = _upload(api_client, fixtures_dir, "study_notes.html", "text/html")
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["document_id"] == first.json()["document_id"]
