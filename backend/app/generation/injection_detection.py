"""Lightweight prompt-injection signal detection for retrieved evidence.

Spec section 8D.3: "Where practical, implement a lightweight detection
layer for obvious injection patterns... Detection must NOT be treated as a
complete defense... a document should not be rejected merely because it
contains words like 'ignore' in normal academic content."

This module never blocks, rejects, or alters a request — it only reports a
signal so callers can log it (spec section 8Q: "suspicious prompt injection
detection" is a loggable security event). The actual defense against
prompt injection is `app.generation.prompts`/`app.study.prompts`' evidence-
is-data framing plus `app.generation.prompt_security`'s marker
neutralization and `app.generation.citations`' backend-controlled citation
validation — this module is a detection/observability layer on top of
those, not a replacement for them.

Deliberately simple, context-aware-ish heuristics (a small set of multi-
word phrases that have essentially no legitimate use in course material,
scored by how many distinct phrases match) rather than single keywords —
"ignore" or "system" alone appear constantly in ordinary academic text
(e.g. "the immune system", "ignore the sign") and must not trigger a
false positive on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Each pattern targets a multi-word phrase shape strongly associated with
# prompt-injection attempts, not a single common word, to keep the false
# positive rate low on ordinary academic text (spec section 8D.3: "avoid
# aggressive false-positive filtering").
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(all\s+)?(previous|prior|the\s+above)\s+instructions", re.I),
    ),
    (
        "reveal_system_prompt",
        re.compile(r"reveal\s+(your|the)\s+(system\s+)?(prompt|instructions)", re.I),
    ),
    ("developer_mode", re.compile(r"\b(developer|debug|admin)\s+mode\b", re.I)),
    (
        "disregard_rules",
        re.compile(
            r"disregard\s+(the\s+)?(above|previous|prior|these)\s+(rules|instructions)", re.I
        ),
    ),
    (
        "act_as_persona",
        re.compile(r"you\s+are\s+now\s+(a|an|in)\b", re.I),
    ),
    (
        "exfiltrate_secrets",
        re.compile(r"(reveal|print|output|leak)\s+(the\s+)?(api\s*key|env(ironment)?\s*var)", re.I),
    ),
    (
        "external_fetch",
        re.compile(r"\b(fetch|curl|download|POST)\s+https?://", re.I),
    ),
)


@dataclass(frozen=True)
class InjectionSignal:
    chunk_id: str
    matched_patterns: tuple[str, ...]

    @property
    def score(self) -> float:
        """0..1 — a crude confidence proxy (more distinct matched phrase
        shapes = higher confidence this is an injection attempt rather than
        coincidental phrasing), not a calibrated probability."""
        return min(1.0, len(self.matched_patterns) / 3)


def detect_injection_signals(chunk_id: str, text: str) -> InjectionSignal | None:
    """Scan one chunk's text for injection-shaped phrases. Returns `None`
    when nothing matched (the common case) rather than a zero-signal
    object, so callers can `if signal:` without an extra attribute check."""
    matched = tuple(name for name, pattern in _INJECTION_PATTERNS if pattern.search(text))
    if not matched:
        return None
    return InjectionSignal(chunk_id=chunk_id, matched_patterns=matched)


def scan_evidence_for_injection_signals(
    evidence: list[tuple[str, str]],
) -> list[InjectionSignal]:
    """Scan a batch of (chunk_id, content) pairs. Used at the point evidence
    is about to enter a prompt (see `app.api.chat`/`app.api.study`) so a
    detection is logged with the same request context as the query that
    triggered it."""
    signals = []
    for chunk_id, content in evidence:
        signal = detect_injection_signals(chunk_id, content)
        if signal is not None:
            signals.append(signal)
    return signals
