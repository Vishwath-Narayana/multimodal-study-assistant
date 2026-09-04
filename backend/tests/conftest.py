from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.parsers.docling_parser import DoclingParser
from app.ingestion.repository import ChunkRepository, DocumentRepository, get_connection, init_db
from app.ingestion.service import IngestionService
from app.ingestion.storage import DataPaths, FileImageStorage
from app.main import create_app

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def ingestion_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolate a test's data directory and SQLite database under tmp_path."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'app.db'}")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def ingestion_service(ingestion_env: Path) -> IngestionService:
    settings = get_settings()
    data_paths = DataPaths(settings.data_dir)
    image_storage = FileImageStorage(data_paths)
    parser = DoclingParser(image_storage=image_storage)

    conn = get_connection(settings.sqlite_path)
    init_db(conn)

    return IngestionService(
        parser=parser,
        document_repo=DocumentRepository(conn),
        chunk_repo=ChunkRepository(conn),
        data_paths=data_paths,
        supported_extensions=tuple(settings.supported_extensions_raw.split(",")),
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        chunking_config=ChunkingConfig(
            target_tokens=settings.chunk_target_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        ),
    )


@pytest.fixture
def api_client(ingestion_env: Path) -> TestClient:
    return TestClient(create_app())
