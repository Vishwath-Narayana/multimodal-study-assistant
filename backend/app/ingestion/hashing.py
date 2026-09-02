"""Content hashing for document identity and duplicate detection.

Implementation choice: the document id is derived directly from the
SHA-256 of the file's bytes (see docs/architecture/ingestion.md). This
makes "is this the same file" a primary-key lookup rather than a separate
duplicate-detection query, and it is not a behavior specified by EduRAG.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(read_chunk: Callable[[], bytes]) -> str:
    """Hash data pulled from a callable in bounded-size chunks.

    Used to avoid holding two full copies of a large file in memory when a
    stream is available instead of an in-memory buffer.
    """
    digest = hashlib.sha256()
    while True:
        chunk = read_chunk()
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def document_id_from_hash(file_hash: str) -> str:
    """Derive the stable document identity from its content hash."""
    return file_hash
