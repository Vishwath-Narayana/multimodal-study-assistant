from __future__ import annotations

import io
import sqlite3
import wave
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.ingestion.repository import get_connection, init_db


@pytest.fixture
def db_conn(ingestion_env: Path) -> sqlite3.Connection:
    """Mirrors `tests.multimodal.conftest.db_conn` — a migrated SQLite
    connection under the isolated test data dir. Duplicated rather than
    imported across test packages (pytest fixtures are directory-scoped by
    conftest location)."""
    settings = get_settings()
    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    return conn


@pytest.fixture
def wav_bytes() -> bytes:
    """Mirrors `tests.multimodal.conftest.wav_bytes` — a tiny, valid,
    silent mono WAV file."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    return buffer.getvalue()
