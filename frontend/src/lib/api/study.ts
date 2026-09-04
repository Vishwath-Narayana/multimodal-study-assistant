import { apiPost } from "./client";
import type {
  CompareRequest,
  CompareResponse,
  ExplainRequest,
  ExplainResponse,
  FlashcardsRequest,
  FlashcardsResponse,
  MCQRequest,
  MCQResponse,
  QuizRequest,
  QuizResponse,
  SummaryRequest,
  SummaryResponse,
} from "./types";

export function studySummary(request: SummaryRequest): Promise<SummaryResponse> {
  return apiPost<SummaryResponse>("/study/summary", request);
}

export function studyExplain(request: ExplainRequest): Promise<ExplainResponse> {
  return apiPost<ExplainResponse>("/study/explain", request);
}

export function studyCompare(request: CompareRequest): Promise<CompareResponse> {
  return apiPost<CompareResponse>("/study/compare", request);
}

export function studyQuiz(request: QuizRequest): Promise<QuizResponse> {
  return apiPost<QuizResponse>("/study/quiz", request);
}

export function studyMCQ(request: MCQRequest): Promise<MCQResponse> {
  return apiPost<MCQResponse>("/study/mcq", request);
}

export function studyFlashcards(request: FlashcardsRequest): Promise<FlashcardsResponse> {
  return apiPost<FlashcardsResponse>("/study/flashcards", request);
}
