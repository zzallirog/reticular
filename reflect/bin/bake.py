#!/usr/bin/env python3
"""One-pass narrative bake for reticular Reflect.

The request path is cache-only for Claude models (narrator.py): without this
pass a fresh install with the default `sonnet` narrator serves the template
paragraph forever. ONE Claude call runs over the already-built engine — the
engine counts every figure and derives each view's qualitative shape — and
writes the prose cache for all (period x host) views. A single model pass,
NOT a fan-out: one call per view would trip the Claude subscription session
limit. Run on demand or from a daily timer.

    cd reflect && python3 bin/bake.py          # sonnet (default floor)
    cd reflect && python3 bin/bake.py opus     # the max-one-opus audit pass

Numbers stay counted by the engine; the model writes only qualitative prose,
with numbers banned from the prompt (invariant #1).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.batchparse import BATCH_HEADER, parse_sections  # noqa: E402
from engine.config import Settings  # noqa: E402
from engine.narrator import (  # noqa: E402
    NarrativeCache,
    bake as claude_bake,
    is_claude_model,
)
from engine.service import RecapService  # noqa: E402

PERIODS = [0, 1, 3, 6, 12]
HOSTS = ["all", "local", "remote"]


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else Settings().atlas_model
    if not is_claude_model(model):
        print(f"model {model!r} is not a Claude model — one-pass bake needs the claude CLI")
        return

    svc = RecapService(Settings())
    views: list[str] = []
    shapes: list[str] = []
    prompts: dict[str, str] = {}
    for months in PERIODS:
        for host in HOSTS:
            svc.invalidate()
            snap = svc.snapshot(months=months, host=host)
            view = f"{months}:{host}"
            views.append(view)
            shapes.append(f"<<<{view}>>>\n{svc._narrative_shape(snap, months, host)}")
            prompts[view] = svc._narrative_prompt(snap, months, host)

    batch = BATCH_HEADER + "\n" + "\n".join(shapes)
    print(f"one pass: {model} over {len(views)} views ...")
    t0 = time.time()
    resp = claude_bake(batch, model, timeout_s=240)
    dt = time.time() - t0
    if not resp:
        print(
            f"one-pass bake returned nothing ({dt:.1f}s) — Claude CLI unavailable "
            f"(session limit?). Re-run after it resets; already-baked views stay warm."
        )
        return

    cache = NarrativeCache(Settings().narrative_cache_path)

    def absorb(response: str, wanted: set[str]) -> set[str]:
        """Parse a batch response and cache each non-empty paragraph.
        parse_sections drops empty/unknown keys; serialization residue is
        sanitized off and reported, never cached."""
        residue: dict[str, str] = {}
        got = parse_sections(response, wanted, residue=residue)
        for view, junk in residue.items():
            print(f"  sanitized {view}: stripped {junk[:60]!r}")
        for view, prose in got.items():
            cache.put(view, prompts[view], prose, model)
        return set(got)

    written = absorb(resp, set(views))
    print(f"one pass done in {dt:.1f}s: {len(written)}/{len(views)} views written by {model}")

    # A long batch can truncate before every marker is emitted. Retry ONCE over
    # just the dropped views — bounded cleanup, never per-view fan-out.
    missing = [v for v in views if v not in written]
    if missing:
        print(f"retry pass over {len(missing)} dropped view(s): {', '.join(missing)}")
        retry_batch = BATCH_HEADER + "\n" + "\n".join(
            shapes[views.index(v)] for v in missing
        )
        resp2 = claude_bake(retry_batch, model, timeout_s=240)
        if resp2:
            written |= absorb(resp2, set(missing))
            missing = [v for v in views if v not in written]

    if missing:
        print("still no paragraph for:", ", ".join(missing), "— left on template")


if __name__ == "__main__":
    main()
