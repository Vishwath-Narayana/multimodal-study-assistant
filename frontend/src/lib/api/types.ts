// Mirrors backend Pydantic schemas (see backend/app/schemas/*.py). Kept as
// thin TypeScript interfaces, not re-derived generically, so this file
// reads next to the backend schema it mirrors.

// --- Documents (backend/app/schemas/documents.py) --------------------------

export interface DocumentResponse {
  id: string;
  filename: string;
  file_type: string;
  file_hash: string;
  status: "completed" | "duplicate" | "failed" | string;
  uploaded_at: string;
  updated_at: string;
  page_count: number | null;
  title: string | null;
  author: string | null;
  subject: string | null;
  block_count: number | null;
  chunk_count: number | null;
  error_message: string | null;
}

export interface IngestionResult {
  document_id: string;
  filename: string;
  status: "completed" | "duplicate" | "failed" | string;
  page_count: number | null;
  block_count: number;
  chunk_count: number;
  duplicate: boolean;
  error_message: string | null;
}

export interface ArtifactResponse {
  id: string;
  document_id: string;
  chunk_id: string | null;
  artifact_type: "image" | "audio" | string;
  storage_path: string;
  mime_type: string | null;
  sha256: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

// --- Shared evidence / citation shapes --------------------------------------
// Chat's EvidenceItemResponse is a superset of Study's (attribution_score/
// rank + ocr_text/vlm_description/original_artifact/table_content). One
// union type covers both call sites' optional fields.

export interface EvidenceItem {
  chunk_id: string;
  document_id: string;
  filename: string | null;
  page: number | null;
  section: string | null;
  rank: number;
  retrieval_source: string;
  content_preview: string;
  rerank_score?: number | null;
  attribution_score?: number | null;
  attribution_rank?: number | null;
  chunk_type?: string | null;
  audio_start?: number | null;
  audio_end?: number | null;
  ocr_text?: string | null;
  vlm_description?: string | null;
  original_artifact?: string | null;
  table_content?: string[][] | null;
}

export interface Citation {
  chunk_id: string;
  valid: boolean;
  status: string;
  document_id: string | null;
  filename: string | null;
  page: number | null;
  section: string | null;
  chunk_type?: string | null;
  audio_start?: number | null;
  audio_end?: number | null;
}

export interface Sufficiency {
  sufficient: boolean;
  reason: string;
}

export interface Conflict {
  chunk_id_a: string;
  chunk_id_b: string;
  description: string;
}

export interface Contradictions {
  has_conflict: boolean;
  conflicts: Conflict[];
}

// --- Chat (backend/app/schemas/generation.py) -------------------------------

export interface ChatQueryRequest {
  query: string;
  retrieval_mode?: string;
  top_k?: number;
}

export interface ClaimGrounding {
  claim: string;
  supporting_chunk_ids: string[];
  grounding_ratio: number | null;
}

export interface Grounding {
  grounding_ratio: number;
  grounded_token_count: number;
  total_token_count: number;
}

export interface ChatQueryResponse {
  request_id: string;
  query: string;
  answer: string;
  answerable: boolean;
  sufficiency: Sufficiency;
  evidence: EvidenceItem[];
  citations: Citation[];
  grounding: Grounding | null;
  claim_groundings: ClaimGrounding[];
  contradictions: Contradictions;
  timing: { total_ms: number; [key: string]: number | null };
}

// --- Study (backend/app/schemas/study.py) -----------------------------------

export type RetrievalMode =
  | "bm25"
  | "dense"
  | "dense_hyde"
  | "hybrid_rrf"
  | "hybrid_rrf_hyde"
  | "full_baseline";

export interface StudyScope {
  retrieval_mode?: RetrievalMode;
  top_k?: number;
  document_id?: string | null;
}

export interface StudyTrace {
  provider: string;
  model: string;
  stats: {
    requested_count: number | null;
    generated_count: number;
    validated_count: number;
    rejected_count: number;
    duplicate_count: number;
  };
  timing: { total_ms: number; [key: string]: number | null };
}

export interface SummaryRequest extends StudyScope {
  query: string;
  length?: "concise" | "standard" | "detailed";
}

export interface SummaryItem {
  content: string;
  citations: Citation[];
  source_chunk_ids: string[];
}

export interface SummaryResponse {
  request_id: string;
  mode: string;
  query: string;
  answerable: boolean;
  reason: string | null;
  item: SummaryItem | null;
  evidence: EvidenceItem[];
  sufficiency: Sufficiency;
  contradictions: Contradictions;
  trace: StudyTrace;
}

export interface ExplainRequest extends StudyScope {
  query: string;
  style?: "simple" | "standard" | "detailed";
}

export type ExplainResponse = SummaryResponse;

export interface CompareRequest {
  topic_a: string;
  topic_b: string;
  retrieval_mode?: RetrievalMode;
  top_k?: number;
  document_id?: string | null;
}

export interface ComparisonAspect {
  aspect: string;
  topic_a: string | null;
  topic_b: string | null;
  citations: Citation[];
  source_chunk_ids: string[];
}

export interface ComparisonItem {
  topic_a: string;
  topic_b: string;
  aspects: ComparisonAspect[];
  incomplete_for: string[];
}

export interface CompareResponse {
  request_id: string;
  mode: string;
  query: string;
  answerable: boolean;
  reason: string | null;
  item: ComparisonItem | null;
  evidence: EvidenceItem[];
  sufficiency: Sufficiency;
  contradictions: Contradictions;
  trace: StudyTrace;
}

export interface QuizRequest extends StudyScope {
  query: string;
  count?: number;
  difficulty?: "easy" | "medium" | "hard";
  question_type?: "factual_recall" | "conceptual" | "application" | "comparison";
}

export interface QuizQuestion {
  question: string;
  expected_answer: string;
  explanation: string;
  difficulty: string;
  question_type: string;
  citations: Citation[];
  source_chunk_ids: string[];
}

export interface QuizResponse {
  request_id: string;
  mode: string;
  query: string;
  answerable: boolean;
  reason: string | null;
  items: QuizQuestion[];
  evidence: EvidenceItem[];
  sufficiency: Sufficiency;
  contradictions: Contradictions;
  trace: StudyTrace;
}

export interface MCQRequest extends StudyScope {
  query: string;
  count?: number;
  difficulty?: "easy" | "medium" | "hard";
}

export interface MCQOption {
  id: string;
  text: string;
}

export interface MCQItem {
  question: string;
  options: MCQOption[];
  correct_option: string;
  explanation: string;
  difficulty: string;
  citations: Citation[];
  source_chunk_ids: string[];
}

export interface MCQResponse {
  request_id: string;
  mode: string;
  query: string;
  answerable: boolean;
  reason: string | null;
  items: MCQItem[];
  evidence: EvidenceItem[];
  sufficiency: Sufficiency;
  contradictions: Contradictions;
  trace: StudyTrace;
}

export interface FlashcardsRequest extends StudyScope {
  query: string;
  count?: number;
  difficulty?: "easy" | "medium" | "hard";
}

export interface Flashcard {
  front: string;
  back: string;
  explanation: string | null;
  difficulty: string;
  citations: Citation[];
  source_chunk_ids: string[];
}

export interface FlashcardsResponse {
  request_id: string;
  mode: string;
  query: string;
  answerable: boolean;
  reason: string | null;
  items: Flashcard[];
  evidence: EvidenceItem[];
  sufficiency: Sufficiency;
  contradictions: Contradictions;
  trace: StudyTrace;
}
