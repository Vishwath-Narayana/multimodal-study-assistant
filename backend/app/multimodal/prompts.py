"""Controlled VLM prompt (spec section 9).

One centralized template, the same discipline as `app.retrieval.prompts`/
`app.generation.prompts`: the model is instructed to describe only what is
visible, preserve technical terminology, and explicitly flag uncertainty
rather than invent unreadable labels or hidden information.
"""

from __future__ import annotations

VISION_SYSTEM_INSTRUCTIONS = """You are describing an image extracted from a student's study \
material (a slide, textbook figure, or diagram) for a retrieval system. Follow these rules \
strictly:

1. Describe only what is visibly present in the image. Do not invent content.
2. Identify labels, axis titles, legends, and captions exactly as they appear, if legible.
3. For diagrams: describe components, arrows/relationships, and process flow shown.
4. Preserve technical terminology and notation exactly as written (do not paraphrase terms).
5. If any text or detail is not clearly legible, say so explicitly (e.g. "text is too small to \
read") rather than guessing at what it might say.
6. Clearly distinguish text you can read directly from meaning you are inferring — use phrasing \
like "the diagram appears to show..." for inferred relationships.
7. Do not speculate about information the image does not contain."""


def render_vision_prompt(context: str) -> str:
    """`context` is the surrounding section/heading text, if any — used only
    to help the model use consistent terminology, never presented as fact
    about the image (see `app.multimodal.interfaces.VisionProvider`)."""
    if context.strip():
        return (
            f"{VISION_SYSTEM_INSTRUCTIONS}\n\nDocument context this image appears near "
            f'(for terminology only, not a description of the image): "{context.strip()}"\n\n'
            "Describe this image following the rules above."
        )
    return f"{VISION_SYSTEM_INSTRUCTIONS}\n\nDescribe this image following the rules above."
