const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface IngestionResult {
  document_id: string;
  filename: string;
  status: string;
  page_count: number | null;
  block_count: number;
  chunk_count: number;
  duplicate: boolean;
  error_message: string | null;
}

export class ApiError extends Error {}

export async function uploadDocument(file: File): Promise<IngestionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail ?? `Upload failed (${response.status}).`);
  }

  return response.json();
}
