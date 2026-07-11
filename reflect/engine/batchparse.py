"""Batched-prose idiom: one model call, many keyed sections, counted contract.

Self-contained (stdlib only) so the idiom can travel: a caller packs N keyed
blocks under `<<<key>>>` markers into ONE prompt, the model answers with the
same markers, and this module splits, validates and counts the result. Grown in
reticular's Reflect bake (invariant #1: numbers never go through the model);
the checks are counted, not judged — a violation is a regex hit you can point
at, not an opinion.

Contract a response is held to:
- every requested key comes back exactly once (missing keys -> retry-over-
  missing upstream: ONE bounded cleanup call, never per-key fan-out);
- prose carries no digits (the surrounding UI renders counted figures;
  the paragraph narrates shape only);
- prose is addressed to the reader (second person) and stays paragraph-sized.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MARKER_RE = re.compile(r"(?m)^\s*<<<\s*(.+?)\s*>>>\s*$")

BATCH_HEADER = (
    "You are writing personal 'Reflect' recap paragraphs about a developer's "
    "time with an AI coding agent — one paragraph per view listed below. Second "
    "person, warm but precise, 3-4 sentences each, no hype, no lists.\n"
    "IMPORTANT: do NOT state any exact numbers, counts, or percentages — those "
    "render as counted figures beside each paragraph. Narrate SHAPE and THREADS.\n"
    "Vary your openers and closers across paragraphs — these render side by "
    "side on one dashboard, repeated phrasing reads as template.\n"
    "EVERY paragraph must address the developer directly as 'you' — a "
    "paragraph without 'you' in it is a defect (measured: batch mode drifts "
    "into third-person observation without this anchor).\n"
    "Each view is introduced by a `<<<key>>>` marker. Reply with each paragraph "
    "preceded by its EXACT `<<<key>>>` marker on its own line, and nothing else.\n"
)

# Model output edges sometimes carry tool-call serialization residue
# (observed live: a paragraph ending in `</parameter>\n</invoke>`). Each
# anchor marks text that can never be prose — sanitize cuts at the FIRST
# anchor hit and reports what fell, so the strip is counted, not silent.
_RESIDUE_ANCHORS = re.compile(
    r"</?(?:parameter|invoke|function_calls?|antml[:\w]*)\b[^>]*>"
    r"|&lt;/?(?:parameter|invoke|function_calls?)\b[^&]*&gt;"
)


def sanitize(prose: str) -> tuple[str, str]:
    """Strip serialization residue from a paragraph. Returns (clean, stripped);
    `stripped` is empty when the paragraph was already clean."""
    m = _RESIDUE_ANCHORS.search(prose)
    if not m:
        return prose.strip(), ""
    return prose[: m.start()].strip(), prose[m.start():].strip()


# Digits in prose break invariant #1. Spelled-out smalls ("a few", "three")
# are shape, not figures — only literal digit runs and percents count.
_NUMBER_RE = re.compile(r"\d+(?:[.,:]\d+)*\s*%?")
_SECOND_PERSON_RE = re.compile(r"\b[Yy]ou(?:r|'re|'ve|'d|'ll)?\b")
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")


def build_batch(blocks: dict[str, str], header: str = BATCH_HEADER) -> str:
    """Pack {key: block} into one marker-delimited prompt."""
    body = "\n".join(f"<<<{k}>>>\n{v}" for k, v in blocks.items())
    return header + "\n" + body


def parse_sections(
    text: str, keys: set[str], residue: dict[str, str] | None = None
) -> dict[str, str]:
    """Split a `<<<key>>>\\n paragraph` response into {key: paragraph}.

    Unknown keys and empty bodies are dropped; any preamble before the first
    marker is ignored. Later duplicates of a key win (models occasionally
    restate a section — the restatement is the completed one). Every body is
    sanitized; pass `residue` to receive {key: stripped_text} for the
    paragraphs that carried serialization junk (counted, never silent)."""
    parts = MARKER_RE.split(text)
    out: dict[str, str] = {}
    it = iter(parts[1:])
    for key, body in zip(it, it):
        k = key.strip()
        b, stripped = sanitize(body)
        if stripped and residue is not None:
            residue[k] = stripped
        if k in keys and b:
            out[k] = b
    return out


@dataclass
class SectionAudit:
    """Counted contract-check of one returned section."""

    key: str
    chars: int
    sentences: int
    number_hits: list[str]  # literal digit/percent tokens found (invariant #1)
    second_person: bool

    @property
    def clean(self) -> bool:
        return not self.number_hits


def audit_section(key: str, prose: str) -> SectionAudit:
    return SectionAudit(
        key=key,
        chars=len(prose),
        sentences=len(_SENTENCE_RE.findall(prose)),
        number_hits=_NUMBER_RE.findall(prose),
        second_person=bool(_SECOND_PERSON_RE.search(prose)),
    )


def audit_response(text: str, keys: set[str]) -> dict:
    """Counted summary of one raw batch response against the requested keys.

    Everything here is a count or a literal token list — the caller can print
    it as provenance without any model in the loop."""
    residue: dict[str, str] = {}
    got = parse_sections(text, keys, residue=residue)
    raw_markers = [m.strip() for m in MARKER_RE.findall(text)]
    audits = {k: audit_section(k, v) for k, v in got.items()}
    return {
        "requested": len(keys),
        "returned": len(got),
        "missing": sorted(keys - set(got)),
        "stray_markers": sorted(set(raw_markers) - keys),
        "residue_stripped": residue,
        "number_violations": {
            k: a.number_hits for k, a in audits.items() if a.number_hits
        },
        "not_second_person": sorted(
            k for k, a in audits.items() if not a.second_person
        ),
        "sections": audits,
    }
