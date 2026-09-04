import { useRef, useState } from "react";
import { ApiError, uploadDocument } from "../../lib/api";
import { SUPPORTED_UPLOAD_EXTENSIONS } from "../../lib/api/documents";
import type { IngestionResult } from "../../lib/api";

interface UploadZoneProps {
  onUploaded: (result: IngestionResult) => void;
}

export function UploadZone({ onUploaded }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadingName, setUploadingName] = useState<string | null>(null);

  async function handleFile(file: File) {
    setStatus("uploading");
    setUploadingName(file.name);
    setErrorMessage(null);
    try {
      const result = await uploadDocument(file);
      setStatus("idle");
      onUploaded(result);
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploadingName(null);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) void handleFile(file);
        }}
        disabled={status === "uploading"}
        className={`flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-14 text-center transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
          isDragOver ? "border-accent bg-surface" : "border-border bg-surface hover:border-accent"
        }`}
      >
        <p className="text-sm text-text">
          {status === "uploading"
            ? `Processing document — ${uploadingName}…`
            : "Drag and drop, or click to select study material"}
        </p>
        <p className="text-xs text-text-muted">
          PDF, DOCX, PPTX, HTML, or audio (WAV, MP3, M4A)
        </p>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={SUPPORTED_UPLOAD_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />
      {status === "error" && (
        <p role="alert" className="mt-2 text-xs text-red-400">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
