from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_hash: str
    status: str
    uploaded_at: str
    updated_at: str
    page_count: int | None = None
    title: str | None = None
    author: str | None = None
    subject: str | None = None
    block_count: int | None = None
    chunk_count: int | None = None
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class IngestionResultResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int | None = None
    block_count: int
    chunk_count: int
    duplicate: bool
    error_message: str | None = None
