import { studySummary } from "../../lib/api";
import { GenerativePanel } from "../../components/study/GenerativePanel";

const LENGTH_OPTIONS = [
  { value: "concise", label: "Concise" },
  { value: "standard", label: "Standard" },
  { value: "detailed", label: "Detailed" },
] as const;

export function SummaryTab() {
  return (
    <GenerativePanel
      title="Summary"
      description="Summarize a document or topic from your study material."
      queryPlaceholder='Summarize this document, or a topic — e.g. "photosynthesis"'
      optionLabel="Length"
      options={LENGTH_OPTIONS}
      defaultOption="standard"
      submit={({ query, option, documentId }) =>
        studySummary({ query, length: option as "concise" | "standard" | "detailed", document_id: documentId })
      }
    />
  );
}
