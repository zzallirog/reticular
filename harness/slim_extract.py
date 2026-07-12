#!/usr/bin/env python3
# slim_extract.py — "how to take slims". Claude Code logs → slim transcripts.
# Input:  ~/.claude/projects/*/*.jsonl  (or --logs DIR)
# Output: slims.jsonl (one object per session) + fingerprint.json (aggregate of tool frequencies).
#
# Slim = strip EVERYTHING except signal:
#   • prose  — your user turns (native words → situation cores + lexicon)
#   • tools  — ordered tool_use (name + short summary input → model cores: what you work with)
# The payload (file contents, long payloads) is STRIPPED — a slim, not a dump.
# Pure stdlib. Runs anywhere with python3.
import sys, os, json, glob, re, argparse

NOISE = ("<local-command-caveat>", "<command-name>", "Caveat:", "<system-reminder>")

def summarize_input(name, inp):
    if not isinstance(inp, dict): return ""
    if "file_path" in inp:   return os.path.basename(str(inp["file_path"]))
    if "notebook_path" in inp: return os.path.basename(str(inp["notebook_path"]))
    if "command" in inp:     return re.sub(r"\s+", " ", str(inp["command"]))[:120]
    if "pattern" in inp:     return "pattern=" + str(inp["pattern"])[:80]
    if "query" in inp:       return "query=" + str(inp["query"])[:80]
    if "prompt" in inp:      return "prompt=" + str(inp["prompt"])[:80]
    if "url" in inp:         return str(inp["url"])[:80]
    keys = list(inp.keys())
    return ",".join(keys[:4])

def user_text(msg):
    c = msg.get("content")
    if isinstance(c, str): return c
    if isinstance(c, list):
        parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p)
    return ""

def is_noise(t):
    s = t.lstrip()[:80]
    return any(s.startswith(n) or n in t[:200] for n in NOISE)

def slim_session(path):
    prose, tools, counts = [], [], {}
    for line in open(path, encoding="utf-8", errors="ignore"):
        try: d = json.loads(line)
        except Exception: continue
        # meta lines (hook/command injections) and sidechain (subagents) are NOT user
        # prose: harvesting them would learn someone else's dialect
        if d.get("isMeta") or d.get("isSidechain"): continue
        t = d.get("type")
        if t == "user":
            txt = user_text(d.get("message", {}))
            txt = txt.strip()
            if txt and not is_noise(txt) and len(txt.split()) >= 2:
                prose.append(txt[:600])
        elif t == "assistant":
            for c in (d.get("message", {}).get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    nm = c.get("name", "?")
                    counts[nm] = counts.get(nm, 0) + 1
                    tools.append({"i": len(tools), "tool": nm,
                                  "sum": summarize_input(nm, c.get("input"))})
    sid = os.path.splitext(os.path.basename(path))[0]
    return {"sid": sid, "n_prose": len(prose), "n_tools": len(tools),
            "prose": prose, "tools": tools, "tool_counts": counts}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--out", default="slims.jsonl")
    ap.add_argument("--min-tools", type=int, default=3, help="skip sessions thinner than N tools")
    a = ap.parse_args()

    files = sorted(glob.glob(os.path.join(a.logs, "*", "*.jsonl")) +
                   glob.glob(os.path.join(a.logs, "*.jsonl")))
    if not files:
        print(f"NO logs in {a.logs} — was claude-kit installed? are there any sessions?", file=sys.stderr)
        sys.exit(1)

    agg, kept = {}, 0
    with open(a.out, "w", encoding="utf-8") as out:
        for f in files:
            try: s = slim_session(f)
            except Exception: continue
            if s["n_tools"] < a.min_tools and s["n_prose"] < 3:
                continue
            kept += 1
            for k, v in s["tool_counts"].items(): agg[k] = agg.get(k, 0) + v
            out.write(json.dumps(s, ensure_ascii=False) + "\n")

    fp = {"sessions": kept, "tool_freq": dict(sorted(agg.items(), key=lambda x: -x[1])),
          "total_tools": sum(agg.values())}
    json.dump(fp, open("fingerprint.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"slims: {kept} sessions → {a.out}")
    print(f"fingerprint (what you work with): {json.dumps(fp['tool_freq'], ensure_ascii=False)}")

if __name__ == "__main__":
    main()
