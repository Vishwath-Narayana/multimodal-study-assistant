import { apiDelete, apiFileUrl, apiGet, apiUpload } from "./client";
import type { ArtifactResponse, DocumentResponse, IngestionResult } from "./types";

export const SUPPORTED_DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".pptx", ".html", ".htm"];
export const SUPPORTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".m4a"];
export const SUPPORTED_UPLOAD_EXTENSIONS = [
  ...SUPPORTED_DOCUMENT_EXTENSIONS,
  ...SUPPORTED_AUDIO_EXTENSIONS,
];

export function uploadDocument(file: File): Promise<IngestionResult> {
  return apiUpload<IngestionResult>("/documents/upload", file);
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const { documents } = await apiGet<{ documents: DocumentResponse[] }>("/documents");
  return documents;
}

export function getDocument(documentId: string): Promise<DocumentResponse> {
  return apiGet<DocumentResponse>(`/documents/${encodeURIComponent(documentId)}`);
}

export function deleteDocument(documentId: string): Promise<void> {
  return apiDelete(`/documents/${encodeURIComponent(documentId)}`);
}

export async function listDocumentArtifacts(documentId: string): Promise<ArtifactResponse[]> {
  const { artifacts } = await apiGet<{ artifacts: ArtifactResponse[] }>(
    `/documents/${encodeURIComponent(documentId)}/artifacts`
  );
  return artifacts;
}

export function artifactFileUrl(artifactId: string): string {
  return apiFileUrl(`/artifacts/${encodeURIComponent(artifactId)}/file`);
}
