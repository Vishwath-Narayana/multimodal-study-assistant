import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteDocument, listDocuments } from "../lib/api";
import type { DocumentResponse } from "../lib/api";

interface UseDocumentsResult {
  documents: DocumentResponse[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  remove: (documentId: string) => Promise<void>;
}

/** Shared document-list state (spec section 23: avoid re-fetching the same
 * document metadata from every page that needs it). */
export function useDocuments(): UseDocumentsResult {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDocuments(await listDocuments());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load documents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const remove = useCallback(async (documentId: string) => {
    await deleteDocument(documentId);
    setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));
  }, []);

  return { documents, loading, error, refresh, remove };
}
