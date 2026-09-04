import { studyExplain } from "../../lib/api";
import { GenerativePanel } from "../../components/study/GenerativePanel";

const STYLE_OPTIONS = [
  { value: "simple", label: "Simple" },
  { value: "standard", label: "Standard" },
  { value: "detailed", label: "Detailed" },
] as const;

export function ExplainTab() {
  return (
    <GenerativePanel
      title="Explain"
      description="Get a grounded explanation of a concept from your study material."
      queryPlaceholder='Explain a concept — e.g. "how does CPU pipelining work?"'
      optionLabel="Style"
      options={STYLE_OPTIONS}
      defaultOption="standard"
      submit={({ query, option, documentId }) =>
        studyExplain({ query, style: option as "simple" | "standard" | "detailed", document_id: documentId })
      }
    />
  );
}
