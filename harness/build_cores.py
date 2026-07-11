#!/usr/bin/env python3
# build_cores.py — эмерж-вывод (emerge.json) → материализованные файлы харнеса.
# emerge.json пишет ДВИЖОК (Claude) после harvest.workflow.js — синтез кандидатов A+B.
# Пишет: cores/NN-*.md (ситуация-ядра) · model-cores/MN-*.md · core-triggers.txt (lex+native чанки).
# Чистый stdlib.
import sys, os, json, re, argparse

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "core"

def regex_from_words(words):
    # native слова → грубый regex-альтернатор (lower, экранируем спецсимволы)
    safe = [re.escape(w.lower()) for w in words if w and len(w) >= 3]
    return "|".join(safe) if safe else "(?!x)x"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emerge", default="emerge.json")
    ap.add_argument("--base", default=os.path.expanduser("~/.claude"))
    a = ap.parse_args()
    if not os.path.exists(a.emerge):
        print(f"нет {a.emerge} — движок должен записать эмерж после harvest-воркфлоу", file=sys.stderr)
        sys.exit(1)
    E = json.load(open(a.emerge, encoding="utf-8"))

    cores_dir = os.path.join(a.base, "overlays/cores")
    mc_dir    = os.path.join(a.base, "overlays/model-cores")
    glados    = os.path.join(a.base, "glados")
    for d in (cores_dir, mc_dir, glados): os.makedirs(d, exist_ok=True)

    trig_lines = ["# cid|||regex(lower промпт)|||when-label|||native_chunk;native_chunk;...",
                  "# ⚠ после правки ситуация-триггеров пересобери: python3 build_embeddings.py"]

    # ситуация-ядра
    for i, c in enumerate(E.get("situation_cores", []), 1):
        cid = str(c.get("id", i)); nm = c.get("name") or c.get("facet", f"core{cid}")[:30]
        words = c.get("native_words", [])
        fn = f"{int(cid):02d}-{slug(nm)}.md"
        open(os.path.join(cores_dir, fn), "w", encoding="utf-8").write(
            f"---\nname: core-{slug(nm)}\ncore: {cid}\nclass: situation-pull\n---\n\n"
            f"# Core {cid} — {nm}\n\n**Осколок.** {c.get('facet','')}\n\n"
            f"**Якорь (сырьё).**\n> {c.get('anchor','')}\n\n"
            f"**Нативная лексика.** {', '.join(words)}\n")
        trig_lines.append(f"{cid}|||{regex_from_words(words)}|||{c.get('facet','')[:40]}|||{';'.join(words)}")

    # model-cores
    for i, m in enumerate(E.get("model_cores", []), 1):
        sign = m.get("signature", f"model-core {i}")
        fn = f"M{i}-{slug(sign)}.md"
        open(os.path.join(mc_dir, fn), "w", encoding="utf-8").write(
            f"---\nname: model-core-{slug(sign)}\nmodel_core: {i}\n"
            f"class: {m.get('klass','structural-pull')}\ngate: {m.get('gate','')}\n---\n\n"
            f"# M{i} — {sign}\n\n**Сигнатура.** {sign}\n\n"
            f"**Якорь (выход).** {m.get('tool_evidence','')}\n\n"
            f"**Gate.** {m.get('gate','')}\n\n**Почему.** {m.get('why','')}\n")

    # дополнительная лексика → дописать в triggers (situation из lexicon)
    for lx in E.get("lexicon", []):
        cid = str(lx.get("core", "")); words = lx.get("words", [])
        if cid and words:
            trig_lines.append(f"{cid}|||{regex_from_words(words)}|||{lx.get('situation','')[:40]}|||{';'.join(words)}")

    open(os.path.join(glados, "core-triggers.txt"), "w", encoding="utf-8").write("\n".join(trig_lines) + "\n")
    print(f"cores: {len(E.get('situation_cores',[]))} · model-cores: {len(E.get('model_cores',[]))} · "
          f"triggers: {len(trig_lines)-2} строк")
    print(f"→ {cores_dir}\n→ {mc_dir}\n→ {os.path.join(glados,'core-triggers.txt')}")
    print("след: python3 build_embeddings.py  (recall-индекс)")

if __name__ == "__main__":
    main()
