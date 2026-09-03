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
    """A migrated SQLite connection under the isolated test data dir
    (reuses the top-level `ingestion_env` fixture for DATA_DIR/DATABASE_URL
    isolation)."""
    settings = get_settings()
    conn = get_connection(settings.sqlite_path)
    init_db(conn)
    return conn


@pytest.fixture
def wav_bytes() -> bytes:
    """A tiny, valid, silent mono WAV file — enough for format validation
    and to exercise the audio pipeline without a real recording."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)  # 0.1s of silence
    return buffer.getvalue()
