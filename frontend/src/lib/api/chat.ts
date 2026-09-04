import { apiPost } from "./client";
import type { ChatQueryRequest, ChatQueryResponse } from "./types";

export function queryChat(request: ChatQueryRequest): Promise<ChatQueryResponse> {
  return apiPost<ChatQueryResponse>("/chat/query", request);
}
