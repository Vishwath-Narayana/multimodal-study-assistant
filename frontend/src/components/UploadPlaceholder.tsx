import { useRef, useState } from "react";
import { ApiError, uploadDocument, type IngestionResult } from "../lib/api";

const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".html", ".htm"];

interface UploadPlaceholderProps {
  onIngested: (result: IngestionResult) => void;
}

export function UploadPlaceholder({ onIngested }: UploadPlaceholderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleFile(file: File) {
    setStatus("uploading");
    setErrorMessage(null);
    try {
      const result = await uploadDocument(file);
      setStatus("idle");
      onIngested(result);
    } catch (err) {
      setStatus("error");
      setErrorMessage(err instanceof ApiError ? err.message : "Upload failed.");
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface px-6 py-16 text-center transition-colors hover:border-accent"
      >
        <p className="text-sm text-text">
          {status === "uploading" ? "Uploading…" : "Click to select study material"}
        </p>
        <p className="text-xs text-text-muted">
          PDF, DOCX, PPTX, or HTML — images and lecture audio come in a later phase
        </p>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={SUPPORTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />
      {status === "error" && (
        <p className="mt-2 text-xs text-red-400">{errorMessage}</p>
      )}
    </div>
  );
}
