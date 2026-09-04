"""API-level Phase 4 coverage: audio dispatch on /documents/upload,
GET /documents/{id}/artifacts, GET /chunks/{id}."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.documents import get_transcription_provider
from app.main import create_app
from tests.multimodal.fakes import FakeTranscriptionProvider


@pytest.fixture
def client_with_transcription(ingestion_env: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_transcription_provider] = lambda: FakeTranscriptionProvider()
    return TestClient(app)


def test_upload_wav_without_transcription_provider_configured_fails_explicitly(
    api_client: TestClient, wav_bytes: bytes
) -> None:
    response = api_client.post(
        "/documents/upload", files={"file": ("lecture.wav", wav_bytes, "audio/wav")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"]


def test_upload_wav_with_transcription_configured_succeeds(
    client_with_transcription: TestClient, wav_bytes: bytes
) -> None:
    response = client_with_transcription.post(
        "/documents/upload", files={"file": ("lecture.wav", wav_bytes, "audio/wav")}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunk_count"] >= 1
    assert body["page_count"] is None


def test_upload_wav_invalid_bytes_returns_400(client_with_transcription: TestClient) -> None:
    response = client_with_transcription.post(
        "/documents/upload", files={"file": ("lecture.wav", b"not audio", "audio/wav")}
    )
    assert response.status_code == 400


def test_list_document_artifacts_for_unknown_document_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/documents/does-not-exist/artifacts")
    assert response.status_code == 404


def test_list_document_artifacts_after_audio_upload(
    client_with_transcription: TestClient, wav_bytes: bytes
) -> None:
    upload = client_with_transcription.post(
        "/documents/upload", files={"file": ("lecture.wav", wav_bytes, "audio/wav")}
    )
    document_id = upload.json()["document_id"]

    response = client_with_transcription.get(f"/documents/{document_id}/artifacts")
    assert response.status_code == 200
    artifacts = response.json()["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "audio"


def test_get_chunk_by_id_returns_multimodal_fields(
    client_with_transcription: TestClient, wav_bytes: bytes
) -> None:
    upload = client_with_transcription.post(
        "/documents/upload", files={"file": ("lecture.wav", wav_bytes, "audio/wav")}
    )
    document_id = upload.json()["document_id"]
    chunk_id = f"{document_id}::chunk::00000"

    response = client_with_transcription.get(f"/chunks/{chunk_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["chunk_type"] == "transcript"
    assert body["audio_start"] == 0.0


def test_get_chunk_by_id_unknown_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/chunks/does-not-exist")
    assert response.status_code == 404


def test_get_artifact_file_returns_bytes(
    client_with_transcription: TestClient, wav_bytes: bytes
) -> None:
    upload = client_with_transcription.post(
        "/documents/upload", files={"file": ("lecture.wav", wav_bytes, "audio/wav")}
    )
    document_id = upload.json()["document_id"]
    artifacts = client_with_transcription.get(f"/documents/{document_id}/artifacts").json()
    artifact_id = artifacts["artifacts"][0]["id"]

    response = client_with_transcription.get(f"/artifacts/{artifact_id}/file")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_get_artifact_file_unknown_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/artifacts/does-not-exist/file")
    assert response.status_code == 404
