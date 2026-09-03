"""SQLite persistence for the `artifacts` provenance table.

Mirrors `app.ingestion.repository`'s style (plain `sqlite3`, no ORM); the
table itself is defined once in `app.ingestion.schema` alongside
`documents`/`chunks` (see docs/architecture/database.md), not in a second
schema file, so the whole schema stays in one place.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from app.multimodal.models import Artifact, ArtifactType


class ArtifactRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, artifact: Artifact) -> Artifact:
        created_at = artifact.created_at or datetime.now(UTC).isoformat()
        self._conn.execute(
            """
            INSERT INTO artifacts (
                id, document_id, chunk_id, artifact_type, storage_path,
                mime_type, sha256, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                chunk_id = excluded.chunk_id,
                storage_path = excluded.storage_path,
                mime_type = excluded.mime_type,
                sha256 = excluded.sha256,
                metadata = excluded.metadata
            """,
            (
                artifact.id,
                artifact.document_id,
                artifact.chunk_id,
                artifact.artifact_type.value,
                artifact.storage_path,
                artifact.mime_type,
                artifact.sha256,
                json.dumps(artifact.metadata) if artifact.metadata else None,
                created_at,
            ),
        )
        self._conn.commit()
        stored = self.get_by_id(artifact.id)
        assert stored is not None
        return stored

    def set_chunk_id(self, artifact_id: str, chunk_id: str) -> None:
        """Backfill `chunk_id` once chunking assigns the final chunk id —
        see `Artifact`'s docstring for why this two-step link exists."""
        self._conn.execute(
            "UPDATE artifacts SET chunk_id = ? WHERE id = ?", (chunk_id, artifact_id)
        )
        self._conn.commit()

    def get_by_id(self, artifact_id: str) -> Artifact | None:
        row = self._conn.execute(
            "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        return _row_to_artifact(row) if row else None

    def list_for_document(self, document_id: str) -> list[Artifact]:
        rows = self._conn.execute(
            "SELECT * FROM artifacts WHERE document_id = ? ORDER BY created_at ASC",
            (document_id,),
        ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def get_for_chunk(self, chunk_id: str) -> Artifact | None:
        row = self._conn.execute(
            "SELECT * FROM artifacts WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()
        return _row_to_artifact(row) if row else None


def _row_to_artifact(row: sqlite3.Row) -> Artifact:
    return Artifact(
        id=row["id"],
        document_id=row["document_id"],
        chunk_id=row["chunk_id"],
        artifact_type=ArtifactType(row["artifact_type"]),
        storage_path=row["storage_path"],
        mime_type=row["mime_type"],
        sha256=row["sha256"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        created_at=row["created_at"],
    )
