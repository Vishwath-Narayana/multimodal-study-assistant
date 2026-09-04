# Phase 8 Security Test Matrix

Every row below was actually executed (`uv run pytest tests/security/`,
plus the pre-existing `tests/generation/test_security.py` /
`tests/multimodal/test_security.py`) on 2026-09-04 against this branch.
`PASS` means the test ran and passed; nothing here is asserted without
having been run. See `docs/security/PHASE_8_SECURITY_REPORT.md` for the
full run output summary.

## Upload attacks

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Path traversal (`../../etc/passwd`) | Filename sanitization | `sanitize_filename` + `DataPaths._resolve_within` | `test_sanitize_filename_rejects_dot_dot_traversal`, `test_path_traversal_filename_never_escapes_data_root` | PASS |
| Windows-style traversal (`..\..\`) | Filename sanitization | `sanitize_filename` | `test_sanitize_filename_rejects_windows_style_traversal` | PASS |
| Absolute path filename | Filename sanitization | `sanitize_filename` (`Path.name`) | `test_sanitize_filename_rejects_absolute_path` | PASS |
| Null byte in filename | Filename sanitization | `sanitize_filename` regex | `test_sanitize_filename_rejects_null_byte` | PASS |
| Unicode-lookalike traversal chars | Filename sanitization | `sanitize_filename` | `test_sanitize_filename_handles_unicode_lookalikes` | PASS |
| Very long filename | Filename sanitization | `sanitize_filename` | `test_sanitize_filename_truncation_of_very_long_name` | PASS |
| Whitespace-only filename | Filename sanitization | `sanitize_filename` fallback (`"upload"`) | `test_sanitize_filename_handles_whitespace_only_name` | PASS |
| Shell metacharacters in filename | Filename sanitization | `sanitize_filename` regex | `test_sanitize_filename_rejects_shell_metacharacters` | PASS |
| Duplicate filename, different documents | Storage | Content-hash document identity | `test_duplicate_filenames_from_different_uploads_do_not_collide` | PASS |
| Unsupported extension | Upload validation | `validate_upload` extension check | `test_upload_rejects_unsupported_extension` | PASS |
| Empty file | Upload validation | `validate_upload` size check | `test_upload_rejects_empty_file` | PASS |
| Oversized file | Upload validation | `max_upload_size_mb` | `test_upload_rejects_oversized_file` | PASS |
| Lying `Content-Type` header | Upload validation | Header never trusted | `test_upload_ignores_client_supplied_content_type` | PASS |
| Content/extension mismatch (MIME) | Upload validation | Magic-byte check (Phase 8) | `test_upload_rejects_content_mismatched_with_extension` | PASS |
| Malformed PDF (correct signature, corrupt body) | Parser | `DocumentParser`/Docling fail-safe | `test_upload_rejects_malformed_pdf` | PASS |
| Duplicate upload (identical bytes) | Ingestion | Content-hash dedup | `test_reuploading_identical_bytes_is_a_duplicate` | PASS |

## Prompt injection

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Direct injection in user query (control chars) | Retrieval choke point | `RetrievalService.retrieve` control-char rejection | `test_query_with_control_characters_is_rejected_before_reaching_a_prompt`, `test_retrieval_service_raises_on_control_character_query` | PASS |
| Direct injection via oversized query | Retrieval choke point | `security_max_query_length` | `test_retrieval_service_raises_on_oversized_query` | PASS |
| Indirect injection in a retrieved chunk ("ignore previous instructions") | Generation prompt | Evidence-is-data framing (Phase 3) | `tests/generation/test_security.py::test_malicious_evidence_text_stays_inside_evidence_section` | PASS |
| Indirect injection via forged section marker | Generation + Study prompts | `neutralize_prompt_markers` (Phase 8) | `test_neutralize_prompt_markers_breaks_reserved_boundaries`, `test_chat_prompt_never_contains_a_forged_section_boundary_from_evidence`, `test_study_prompt_also_neutralizes_forged_markers` | PASS |
| Injection-shaped text arriving as OCR/VLM/transcript content | Generation prompt | Uniform evidence-is-data framing (Phase 3/4) | `test_injection_shaped_ocr_or_vlm_or_transcript_text_stays_in_evidence_section` (parametrized ×3) | PASS |
| Injection via image description (VLM) | Generation prompt | Same as above — VLM description is ordinary chunk content | Covered by the parametrized test above | PASS |
| Planted citation from injected text | Citation validator | `DeterministicCitationValidator` | `tests/generation/test_security.py::test_citation_planted_by_injected_text_is_rejected_if_not_retrieved` | PASS |
| False-positive check: ordinary academic text using "ignore"/"system" | Detection layer | Multi-word phrase patterns, not single keywords | `test_detector_does_not_flag_ordinary_academic_text_using_common_words` | PASS |
| Obvious injection phrase detected (log-only) | Detection layer | `app.generation.injection_detection` | `test_detector_flags_obvious_injection_phrase`, `test_scan_evidence_reports_only_matching_chunks` | PASS |

## Citation attacks

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Fake/hallucinated chunk id | Citation validator | Evidence-set lookup | `test_fake_chunk_id_is_rejected` | PASS |
| Nonexistent chunk id (known corpus) | Citation validator | `UNKNOWN_CHUNK` status | `test_nonexistent_chunk_id_with_known_corpus_is_still_unknown` | PASS |
| Citation to a chunk from a different document/request | Citation validator | `NOT_IN_RETRIEVED_EVIDENCE` status | `test_citation_to_a_chunk_from_a_different_document_not_in_this_request_is_rejected` | PASS |
| Stale citation from a prior request | Citation validator | Per-call evidence scoping (no global state) | `test_stale_citation_from_a_prior_requests_evidence_is_rejected` | PASS |
| Citation not present in retrieved context at all | Citation validator | Evidence-set lookup | `test_citation_not_present_in_retrieved_context_at_all` | PASS |
| Non-standard citation-shaped string | Citation extraction | Strict `[chunk:<id>]` regex, fail-safe | `test_model_cannot_smuggle_a_citation_shaped_string_that_isnt_the_marker_format` | PASS |
| Regression: legitimate citation still valid | Citation validator | — | `test_valid_citation_still_passes` | PASS |

## Resource attacks

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Huge query string | Retrieval choke point | `security_max_query_length` | `test_search_rejects_huge_query` | PASS |
| Huge filename | Filename sanitization | `sanitize_filename` (no length blowup risk) | `test_sanitize_filename_truncation_of_very_long_name` | PASS |
| Out-of-range `top_k` | Retrieval choke point | `security_max_top_k` | `test_search_rejects_out_of_range_top_k`, `test_search_rejects_zero_top_k` | PASS |
| Excessive page count | Ingestion | `security_max_document_pages` | `test_document_exceeding_max_pages_is_rejected` | PASS |
| Excessive extracted text | Ingestion | `security_max_extracted_chars` | `test_document_exceeding_max_extracted_chars_is_rejected` | PASS |
| Document within limits (regression) | Ingestion | — | `test_document_within_limits_passes` | PASS |
| Excessive image/artifact count | Multimodal | `security_max_artifacts_per_document` | `test_image_enrichment_stops_after_configured_artifact_cap` | PASS |
| Excessive image dimensions (decompression bomb) | Multimodal | `validate_image_artifact` (Phase 4) | `tests/multimodal/test_security.py` (pre-existing) | PASS |

## API attacks

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Malformed JSON body | API | FastAPI/Pydantic body parsing | `test_malformed_json_body_returns_422_not_500` | PASS |
| Wrong field type | API | Pydantic schema validation | `test_wrong_field_type_returns_422` | PASS |
| Missing required field | API | Pydantic schema validation | `test_missing_required_field_returns_422` | PASS |
| Path-traversal-shaped ID parameter | API | Route not found / safe 404 | `test_invalid_document_id_returns_404_not_500` | PASS |
| Invalid chunk ID | API | 404, not 500 | `test_invalid_chunk_id_returns_404` | PASS |
| Invalid artifact ID | API | 404, not 500 | `test_invalid_artifact_id_returns_404` | PASS |
| Unsupported HTTP method | API | FastAPI routing (405) | `test_unsupported_http_method_returns_405`, `test_delete_on_read_only_resource_returns_405` | PASS |
| Unrecognized retrieval mode | API | `InvalidModeError` → 400 | `test_unrecognized_retrieval_mode_returns_400_not_500` | PASS |
| Empty query | API | `EmptyQueryError` → 400 | `test_empty_query_returns_400_not_500` | PASS |
| Error response leaks internals | API error handling | Sanitized error responses (Phase 8) | `test_error_responses_never_expose_filesystem_paths` | PASS |
| Unknown route | API | FastAPI default 404 | `test_unknown_route_returns_404` | PASS |
| Out-of-range study `count` / empty corpus | API | `_check_count` / `NoIndexedChunksError` global handler (Phase 8) | `test_study_endpoint_rejects_out_of_range_count` | PASS |
| Domain error types correctly mapped | API dispatch | `_ERROR_STATUS` dicts | `test_retrieval_service_error_types_map_to_400` | PASS |

## Database integrity

| Attack | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Deletion cascade (chunks) | Database | Explicit dependency-ordered delete | `tests/ingestion/test_api_documents.py::test_delete_document_removes_it_and_its_chunks` (pre-existing) | PASS |
| Orphan prevention: deleting doc A leaves doc B's chunks intact | Database | Scoped `DELETE ... WHERE document_id = ?` | `test_deleting_one_document_never_touches_another_documents_chunks` | PASS |
| Orphan prevention: artifacts | Database | Same | `test_deleting_a_document_removes_its_artifacts_but_not_anothers` | PASS |
| Orphan prevention: study_items | Database | Same | `test_deleting_a_document_removes_its_study_items_but_not_anothers` | PASS |
| Invalid reference (delete unknown document) | Database | `delete()` returns `False`, no side effects | `test_deleting_unknown_document_returns_false_and_changes_nothing` | PASS |
| Chunk-id collision within one document | Chunking | Monotonic per-document chunk ordering | `test_chunking_never_produces_duplicate_chunk_ids_for_one_document` | PASS |

## Temporary file cleanup

| Scenario | Component | Mitigation | Test | Result |
|---|---|---|---|---|
| Successful ingestion keeps the file | Ingestion | — (regression guard) | `test_successful_ingestion_keeps_the_raw_file` | PASS |
| Parser failure | Ingestion | `delete_document_files` on failure (Phase 8) | `test_parser_failure_cleans_up_the_raw_file` | PASS |
| Resource-limit rejection | Ingestion | Same cleanup path (Phase 8) | `test_resource_limit_rejection_cleans_up_the_raw_file` | PASS |
| Audio transcription failure | Audio ingestion | `delete_document_files` on failure (Phase 8) | `test_audio_transcription_failure_cleans_up_the_raw_file` | PASS |
| Status/file-existence consistency | Ingestion | Cross-check | `test_ingest_never_leaves_a_document_with_completed_status_but_missing_file` | PASS |

## Not tested / not applicable

| Item | Reason |
|---|---|
| PDF JavaScript execution | NOT APPLICABLE — this application never executes embedded document content of any kind; there is no code path capable of running PDF JavaScript. |
| DOCX/PPTX macro execution | NOT APPLICABLE — same as above; `python-docx`/`python-pptx` read structural XML only. |
| Live SSRF probe against HTML-embedded external resources | NOT TESTED — would require a monitored-network test harness beyond this phase's scope (see `THREAT_MODEL.md` "Document parsing" residual risk). Static analysis found no outbound-HTTP code path in the parsing pipeline. |
| CORS misconfiguration under a real multi-origin deployment | NOT APPLICABLE — this application is local-first single-user; the CORS configuration is documented as a development-appropriate default, not hardened for a hypothetical multi-tenant deployment (out of Phase 8's scope per `THREAT_MODEL.md` Non-Goals). |
| Whether a real LLM actually obeys an injected instruction | NOT TESTED — requires a live model; the default (Ollama-free) test suite cannot exercise this, matching `docs/architecture/generation.md`'s pre-existing documented limitation. |
