"""Structured-output parsing for the Phase 5 Study Engine.

No JSON-from-LLM + schema-validation helper exists elsewhere in this
codebase (every prior LLM interaction is "prompt in, raw string out", then
a regex over the raw text — see `app.generation.citations`). This module is
the equivalent for study modes that ask the model to emit one JSON object
(compare/quiz/mcq/flashcards): extract the object, parse it, and check its
shape field-by-field. On any failure this raises
`app.study.errors.MalformedStudyOutputError` rather than guessing at the
model's intent — the same "fail safe, never best-effort-repair" discipline
`extract_citations` already establishes. This is a *formatting* extraction
(finding the JSON object inside a response that may carry stray
commentary/code fences around it), not a semantic repair of the content
inside it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.study.errors import MalformedStudyOutputError

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Best-effort *location* of the JSON object in `text` — never a
    best-effort repair of its content. Strips a markdown code fence if the
    model wrapped its JSON in one (a purely cosmetic wrapping many local
    models add despite being told not to), then falls back to the first
    `{`..last `}` span if the full text is not valid JSON on its own
    (covers a stray leading/trailing sentence around the object)."""
    stripped = _CODE_FENCE.sub("", text).strip()

    for candidate in (stripped, text.strip()):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        raise MalformedStudyOutputError("Model output was valid JSON but not a JSON object.")

    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise MalformedStudyOutputError(
                f"Model output did not contain a parseable JSON object: {exc}"
            ) from exc
        if isinstance(parsed, dict):
            return parsed
        raise MalformedStudyOutputError("Model output was valid JSON but not a JSON object.")

    raise MalformedStudyOutputError("Model output did not contain a JSON object.")


def _require_list(obj: dict[str, Any], key: str) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        raise MalformedStudyOutputError(f'Expected a JSON array at "{key}".')
    return value


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedStudyOutputError("Expected a string or null.")
    return value


def _citations(item: dict[str, Any]) -> list[str]:
    raw = item.get("citations", [])
    if not isinstance(raw, list) or not all(isinstance(c, str) for c in raw):
        raise MalformedStudyOutputError('"citations" must be a list of strings.')
    return raw


@dataclass
class RawComparisonAspect:
    aspect: str
    topic_a: str | None
    topic_b: str | None
    raw_chunk_ids: list[str]


@dataclass
class RawQuizQuestion:
    question: str
    answer: str
    explanation: str
    raw_chunk_ids: list[str]


@dataclass
class RawMCQOption:
    id: str
    text: str


@dataclass
class RawMCQItem:
    question: str
    options: list[RawMCQOption]
    correct_option: str
    explanation: str
    raw_chunk_ids: list[str]


@dataclass
class RawFlashcard:
    front: str
    back: str
    explanation: str | None
    raw_chunk_ids: list[str]


def parse_comparison(text: str) -> list[RawComparisonAspect]:
    obj = _extract_json_object(text)
    aspects: list[RawComparisonAspect] = []
    for raw in _require_list(obj, "aspects"):
        if not isinstance(raw, dict):
            raise MalformedStudyOutputError('Each item in "aspects" must be a JSON object.')
        aspect = raw.get("aspect")
        if not isinstance(aspect, str):
            raise MalformedStudyOutputError('"aspect" must be a string.')
        aspects.append(
            RawComparisonAspect(
                aspect=aspect,
                topic_a=_str_or_none(raw.get("topic_a")),
                topic_b=_str_or_none(raw.get("topic_b")),
                raw_chunk_ids=_citations(raw),
            )
        )
    return aspects


def parse_quiz(text: str) -> list[RawQuizQuestion]:
    obj = _extract_json_object(text)
    questions: list[RawQuizQuestion] = []
    for raw in _require_list(obj, "questions"):
        if not isinstance(raw, dict):
            raise MalformedStudyOutputError('Each item in "questions" must be a JSON object.')
        question = raw.get("question")
        answer = raw.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            raise MalformedStudyOutputError('"question" and "answer" must be strings.')
        explanation = raw.get("explanation")
        questions.append(
            RawQuizQuestion(
                question=question,
                answer=answer,
                explanation=explanation if isinstance(explanation, str) else "",
                raw_chunk_ids=_citations(raw),
            )
        )
    return questions


def parse_mcqs(text: str) -> list[RawMCQItem]:
    obj = _extract_json_object(text)
    items: list[RawMCQItem] = []
    for raw in _require_list(obj, "items"):
        if not isinstance(raw, dict):
            raise MalformedStudyOutputError('Each item in "items" must be a JSON object.')
        question = raw.get("question")
        correct_option = raw.get("correct_option")
        if not isinstance(question, str) or not isinstance(correct_option, str):
            raise MalformedStudyOutputError('"question" and "correct_option" must be strings.')
        raw_options = raw.get("options")
        if not isinstance(raw_options, list):
            raise MalformedStudyOutputError('"options" must be a list.')
        options: list[RawMCQOption] = []
        for raw_option in raw_options:
            if (
                not isinstance(raw_option, dict)
                or not isinstance(raw_option.get("id"), str)
                or not isinstance(raw_option.get("text"), str)
            ):
                raise MalformedStudyOutputError(
                    'Each option must be a JSON object with string "id" and "text".'
                )
            options.append(RawMCQOption(id=raw_option["id"], text=raw_option["text"]))
        explanation = raw.get("explanation")
        items.append(
            RawMCQItem(
                question=question,
                options=options,
                correct_option=correct_option,
                explanation=explanation if isinstance(explanation, str) else "",
                raw_chunk_ids=_citations(raw),
            )
        )
    return items


def parse_flashcards(text: str) -> list[RawFlashcard]:
    obj = _extract_json_object(text)
    cards: list[RawFlashcard] = []
    for raw in _require_list(obj, "cards"):
        if not isinstance(raw, dict):
            raise MalformedStudyOutputError('Each item in "cards" must be a JSON object.')
        front = raw.get("front")
        back = raw.get("back")
        if not isinstance(front, str) or not isinstance(back, str):
            raise MalformedStudyOutputError('"front" and "back" must be strings.')
        cards.append(
            RawFlashcard(
                front=front,
                back=back,
                explanation=_str_or_none(raw.get("explanation")),
                raw_chunk_ids=_citations(raw),
            )
        )
    return cards
