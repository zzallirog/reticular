#!/usr/bin/env python3
# build_embeddings.py — recall index (leg-3b dense). Native trigger chunks of the situation cores →
# embeddinggemma (ollama) → normalized vectors → core_p2p.json. Asymmetric prefix.
# This is what gives recall REPRODUCIBLE numbers on YOUR vault. Pure stdlib + urllib.
#
# Input:  core-triggers.txt (format: cid|||regex|||when-label|||chunk1;chunk2;...  — native chunks)
#         OR cores/*.md with native_words in frontmatter.
# Output: ~/.claude/glados/core_p2p.json = {"model","cores":{cid:[{chunk,vec}]}}
import sys, os, json, math, urllib.request, argparse

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
MODEL  = os.environ.get("GLADOS_EMBED", "embeddinggemma")  # fallback: nomic-embed-text

def embed(text, prefix):
    req = urllib.request.Request(OLLAMA + "/api/embed",
        data=json.dumps({"model": MODEL, "input": f"{prefix}: {text}"}).encode(),
        headers={"Content-Type": "application/json"})
    v = json.load(urllib.request.urlopen(req, timeout=30))["embeddings"][0]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]

def chunks_from_triggers(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p = line.split("|||")
        if len(p) < 3: continue
        cid = p[0].strip()[:2].lstrip("0") or "0"
        # native chunks in field 4 (;-separated) OR parse regex alternatives as a crude fallback
        native = []
        if len(p) >= 4 and p[3].strip():
            native = [c.strip() for c in p[3].split(";") if c.strip()]
        if not native:
            native = [w for w in p[1].replace("\\", "").replace(".{0,14}", " ").split("|")
                      if w and len(w) > 2 and not any(ch in w for ch in "(){}[]^$*+?")][:12]
        if native: out.setdefault(cid, []).extend(native)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--triggers", default=os.path.expanduser("~/.claude/glados/core-triggers.txt"))
    ap.add_argument("--out", default=os.path.expanduser("~/.claude/glados/core_p2p.json"))
    a = ap.parse_args()

    if not os.path.exists(a.triggers):
        print(f"missing {a.triggers} — run build_cores.py first", file=sys.stderr); sys.exit(1)
    # health-check ollama
    try:
        urllib.request.urlopen(OLLAMA + "/api/tags", timeout=4)
    except Exception:
        print(f"ollama not responding at {OLLAMA} — run `ollama serve` and `ollama pull {MODEL}`",
              file=sys.stderr); sys.exit(2)

    by_core = chunks_from_triggers(a.triggers)
    if not by_core:
        print("no native chunks in triggers → nothing to embed", file=sys.stderr); sys.exit(1)

    index = {"model": MODEL, "cores": {}}
    total = 0
    for cid, chs in by_core.items():
        seen, entries = set(), []
        for ch in chs:
            if ch in seen: continue
            seen.add(ch)
            try: entries.append({"chunk": ch, "vec": embed(ch, "search_document")})
            except Exception as e:
                print(f"  warn: embed fail '{ch[:30]}': {e}", file=sys.stderr); continue
        if entries:
            index["cores"][cid] = entries; total += len(entries)
            print(f"  core {cid}: {len(entries)} chunks")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(index, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"core_p2p.json: {total} vectors, model {MODEL} → {a.out}")
    print("recall index ready. self-test: ida-attest leg-3b now has a backstop.")

if __name__ == "__main__":
    main()
