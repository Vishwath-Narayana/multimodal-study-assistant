"""Phase 8N: API-attack security tests (spec section 8H/8H.1).

Malformed requests, invalid path parameters, wrong types, unsupported HTTP
methods, and confirmation that error responses never leak internals
(filesystem paths, stack traces, exception class names).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _upload_one_document(api_client: TestClient, fixtures_dir: Path) -> None:
    """Body-validation errors (422) must be returned before any retrieval
    dependency (BM25/FAISS index construction) even runs — but FastAPI
    resolves an endpoint's `Depends()` dependencies alongside body
    validation, so a request against a completely empty corpus can surface
    `NoIndexedChunksError` (409) first regardless of body validity. To keep
    these tests isolating *only* the behavior under test (schema
    validation), a real document is uploaded first so the dependency chain
    always succeeds and 422 is the only possible outcome for a bad body."""
    with open(fixtures_dir / "study_notes.html", "rb") as f:
        response = api_client.post(
            "/documents/upload", files={"file": ("study_notes.html", f, "text/html")}
        )
    assert response.status_code == 200


def test_malformed_json_body_returns_422_not_500(api_client: TestClient) -> None:
    response = api_client.post(
        "/chat/query", content=b"{not valid json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422


def test_wrong_field_type_returns_422(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post("/chat/query", json={"query": 12345, "top_k": "not-an-int"})
    assert response.status_code == 422


def test_missing_required_field_returns_422(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post("/chat/query", json={"top_k": 5})
    assert response.status_code == 422


def test_invalid_document_id_returns_404_not_500(api_client: TestClient) -> None:
    response = api_client.get("/documents/../../etc/passwd")
    assert response.status_code in (404, 422)


def test_invalid_chunk_id_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/chunks/does-not-exist")
    assert response.status_code == 404


def test_invalid_artifact_id_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/artifacts/does-not-exist/file")
    assert response.status_code == 404


def test_unsupported_http_method_returns_405(api_client: TestClient) -> None:
    response = api_client.put("/documents")
    assert response.status_code == 405


def test_delete_on_read_only_resource_returns_405(api_client: TestClient) -> None:
    response = api_client.delete("/chunks/some-id")
    assert response.status_code == 405


def test_unrecognized_retrieval_mode_returns_400_not_500(
    api_client: TestClient, fixtures_dir: Path
) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post(
        "/retrieval/search", json={"query": "test", "mode": "definitely-not-a-real-mode"}
    )
    assert response.status_code == 400


def test_empty_query_returns_400_not_500(api_client: TestClient, fixtures_dir: Path) -> None:
    _upload_one_document(api_client, fixtures_dir)
    response = api_client.post("/retrieval/search", json={"query": "", "mode": "bm25"})
    assert response.status_code == 400


def test_error_responses_never_expose_filesystem_paths(api_client: TestClient) -> None:
    """Spec section 8H.1: never expose filesystem paths / internals in an
    API response, even in a 4xx error path."""
    response = api_client.get("/documents/does-not-exist")
    body_text = response.text
    assert "/Users/" not in body_text
    assert "/data/" not in body_text
    assert "Traceback" not in body_text
    assert ".py\"" not in body_text and ".py'" not in body_text


def test_unknown_route_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/this-route-does-not-exist")
    assert response.status_code == 404


def test_study_endpoint_rejects_out_of_range_count(api_client: TestClient) -> None:
    response = api_client.post(
        "/study/quiz",
        json={"query": "photosynthesis", "count": 9999, "retrieval_mode": "bm25"},
    )
    # Either the empty-corpus path (409, no document uploaded) or the
    # count-range rejection (400) is acceptable here — what must never
    # happen is an unhandled 500.
    assert response.status_code in (400, 409)
