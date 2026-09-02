import { ChatPlaceholder } from "../components/ChatPlaceholder";
import { UploadPlaceholder } from "../components/UploadPlaceholder";

export function StudyPage() {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-text">Your study material</h1>
        <p className="mt-1 text-sm text-text-muted">
          Upload documents, then ask grounded questions with citations.
        </p>
      </div>
      <UploadPlaceholder />
      <ChatPlaceholder />
    </div>
  );
}
