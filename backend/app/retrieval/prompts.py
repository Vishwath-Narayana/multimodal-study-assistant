"""Centralized prompt templates for retrieval-time LLM usage.

The **only** permitted LLM usage in Phase 2 is HyDE query expansion (see
docs/architecture/retrieval.md "Scope Boundary") — this module holds that
one prompt so it is never duplicated or drifted across call sites.
"""

from __future__ import annotations

# Deliberately simple and reproducible: asks for a short *hypothetical*
# passage that would plausibly contain the answer, not a final user-facing
# answer (the model is not told to answer the student's question — it is
# told to write the kind of passage a textbook would contain). This is the
# standard HyDE framing (Gao et al., "Precise Zero-Shot Dense Retrieval
# without Relevance Labels") adapted for a study-notes corpus.
HYDE_PROMPT_TEMPLATE = (
    "Write a short, factual passage (2-4 sentences) that would plausibly "
    "appear in a textbook or study notes and directly addresses the "
    "following question. Do not address the reader or mention the "
    "question itself — write only the passage.\n\n"
    "Question: {query}\n\n"
    "Passage:"
)


def render_hyde_prompt(query: str) -> str:
    return HYDE_PROMPT_TEMPLATE.format(query=query)
