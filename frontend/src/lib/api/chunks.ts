import { apiGet } from "./client";

// Mirrors backend/app/schemas/documents.py ChunkResponse (Phase 4 debug
// endpoint) — used here only to resolve an image evidence item's
// `artifact_id` so the evidence panel can build an artifact file URL.
export interface ChunkResponse {
  id: string;
  document_id: string;
  chunk_type: string;
  artifact_id: string | null;
  image_path: string | null;
  table_content: string[][] | null;
  equation_content: string | null;
}

export function getChunk(chunkId: string): Promise<ChunkResponse> {
  return apiGet<ChunkResponse>(`/chunks/${encodeURIComponent(chunkId)}`);
}
