#!/usr/bin/env python3
# build_embeddings.py — recall-индекс (нога-3b dense). Нативные trigger-чанки ситуация-ядер →
# embeddinggemma (ollama) → нормализованные векторы → core_p2p.json. Asymmetric prefix.
# Это то, что даёт recall ВОСПРОИЗВОДИМЫЕ числа на ТВОЁМ вульте. Чистый stdlib + urllib.
#
# Вход: core-triggers.txt (формат: cid|||regex|||when-label|||chunk1;chunk2;...  — native чанки)
#       ИЛИ cores/*.md с native_words в frontmatter.
# Выход: ~/.claude/glados/core_p2p.json = {"model","cores":{cid:[{chunk,vec}]}}
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
        # native чанки в 4-м поле (;-разделены) ИЛИ разобрать regex-альтернативы как грубый fallback
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
        print(f"нет {a.triggers} — сначала build_cores.py", file=sys.stderr); sys.exit(1)
    # health-check ollama
    try:
        urllib.request.urlopen(OLLAMA + "/api/tags", timeout=4)
    except Exception:
        print(f"ollama не отвечает на {OLLAMA} — запусти `ollama serve` и `ollama pull {MODEL}`",
              file=sys.stderr); sys.exit(2)

    by_core = chunks_from_triggers(a.triggers)
    if not by_core:
        print("нет native-чанков в triggers → нечего эмбедить", file=sys.stderr); sys.exit(1)

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
            print(f"  core {cid}: {len(entries)} чанков")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(index, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"core_p2p.json: {total} векторов, модель {MODEL} → {a.out}")
    print("recall-индекс готов. self-test: ida-attest нога-3b теперь имеет backstop.")

if __name__ == "__main__":
    main()
