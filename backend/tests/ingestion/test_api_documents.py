"""Ingestion API: POST /documents/upload, GET /documents, GET /documents/{id}."""

from pathlib import Path

from fastapi.testclient import TestClient


def _upload(client: TestClient, fixtures_dir: Path, filename: str, content_type: str):
    with open(fixtures_dir / filename, "rb") as f:
        return client.post(
            "/documents/upload", files={"file": (filename, f, content_type)}
        )


def test_upload_valid_document_returns_completed(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    response = _upload(api_client, fixtures_dir, "study_notes.html", "text/html")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] > 0
    assert body["duplicate"] is False


def test_upload_unsupported_file_returns_400(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    response = _upload(api_client, fixtures_dir, "unsupported.txt", "text/plain")
    assert response.status_code == 400
    assert "detail" in response.json()


def test_upload_empty_file_returns_400(api_client: TestClient, fixtures_dir: Path) -> None:
    response = _upload(api_client, fixtures_dir, "empty.pdf", "application/pdf")
    assert response.status_code == 400


def test_list_documents_includes_uploaded_document(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    _upload(api_client, fixtures_dir, "study_notes.docx", "application/vnd.openxmlformats")
    response = api_client.get("/documents")
    assert response.status_code == 200
    documents = response.json()["documents"]
    assert any(doc["filename"] == "study_notes.docx" for doc in documents)


def test_get_document_by_id_returns_metadata(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    upload_response = _upload(
        api_client, fixtures_dir, "study_notes.pptx", "application/vnd.ms-powerpoint"
    )
    document_id = upload_response.json()["document_id"]

    response = api_client.get(f"/documents/{document_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert body["status"] == "completed"
    assert body["page_count"] == 2


def test_get_unknown_document_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/documents/does-not-exist")
    assert response.status_code == 404


def test_reuploading_same_bytes_is_reported_as_duplicate(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    first = _upload(api_client, fixtures_dir, "study_notes.html", "text/html")
    second = _upload(api_client, fixtures_dir, "study_notes.html", "text/html")
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert second.json()["document_id"] == first.json()["document_id"]


def test_delete_document_removes_it_and_its_chunks(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    upload_response = _upload(api_client, fixtures_dir, "study_notes.pdf", "application/pdf")
    document_id = upload_response.json()["document_id"]

    delete_response = api_client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 204

    assert api_client.get(f"/documents/{document_id}").status_code == 404
    assert api_client.get(f"/documents/{document_id}/artifacts").status_code == 404


def test_delete_unknown_document_returns_404(api_client: TestClient) -> None:
    response = api_client.delete("/documents/does-not-exist")
    assert response.status_code == 404


def test_reuploading_after_delete_is_not_a_duplicate(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    first = _upload(api_client, fixtures_dir, "study_notes.pptx", "application/vnd.ms-powerpoint")
    document_id = first.json()["document_id"]
    api_client.delete(f"/documents/{document_id}")

    second = _upload(api_client, fixtures_dir, "study_notes.pptx", "application/vnd.ms-powerpoint")
    assert second.json()["duplicate"] is False
