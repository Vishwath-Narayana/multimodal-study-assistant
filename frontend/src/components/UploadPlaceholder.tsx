export function UploadPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-surface px-6 py-16 text-center">
      <p className="text-sm text-text">Drop study material here</p>
      <p className="text-xs text-text-muted">
        PDF, DOCX, PPTX, images, or lecture audio — coming in a later phase
      </p>
    </div>
  );
}
