import { useState } from "react";
import { ChatPlaceholder } from "../components/ChatPlaceholder";
import { IngestedDocuments } from "../components/IngestedDocuments";
import { UploadPlaceholder } from "../components/UploadPlaceholder";
import type { IngestionResult } from "../lib/api";

export function StudyPage() {
  const [documents, setDocuments] = useState<IngestionResult[]>([]);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Your study material</h1>
        <p className="mt-1 text-sm text-text-muted">
          Upload documents, then ask grounded questions with citations.
        </p>
      </div>
      <UploadPlaceholder onIngested={(result) => setDocuments((prev) => [result, ...prev])} />
      <IngestedDocuments documents={documents} />
      <ChatPlaceholder />
    </div>
  );
}
