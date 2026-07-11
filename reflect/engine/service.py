"""RecapService — a "Reflect"-style monthly recap over Claude Code session logs.

Where ClaudeUsageService answers *how much* (tokens, cost), this answers *what
the work became*. It does its own single walk over ~/.claude/projects/**/*.jsonl
because it needs signal the usage parser discards: user-turn text (framing,
push-back), tool_use blocks (delegation), and per-session shape. It then joins
the vault (proj_*.md `originSessionId` / `part_of`) so cwd fragments collapse
into named threads with an outcome — the layer a raw heatmap can't give.

Skills are detected structurally (counts of tool calls, opening-turn length,
correction turns), never asked of an LLM — the number earns the claim. Only the
closing narrative paragraph is generated, with a templated fallback.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .base import BaseService
from .config import Settings
from .jsonl_helpers import _iter_jsonl, _parse_ts
from .models import (
    ErrStreak,
    FileChurn,
    FrictionStat,
    HostCoverage,
    ProjectArc,
    PulseDay,
    RecapSnapshot,
    RecapStat,
    RhythmBin,
    SkillEvidence,
    StatCard,
    ToolCount,
    TopicShare,
    TopicSpark,
)
from .ollama import OllamaClient, OllamaError
from .narrator import NarrativeCache, is_claude_model
from .factbank import FactBank

_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Correction / push-back markers (RU + EN), matched on word boundaries so
# "нет" doesn't fire inside "интернет". Heuristic — surfaced as such.
_PUSHBACK_RE = re.compile(
    r"(?<![\w])(нет|неверно|не так|не то|не совсем|неправ|стоп|погоди|стой|"
    r"wrong|incorrect|actually|not quite|no,)(?![\w])",
    re.IGNORECASE,
)
_FRAMING_CHARS = 280  # an opening user turn longer than this counts as "framing first"
_NARRATIVE_MODEL_FALLBACK = "qwen2.5:7b"
_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}  # churn = rewrites, not reads
_INTERRUPT_PREFIX = "[Request interrupted"  # Claude Code's own marker text
_TAG_RE = re.compile(r"<[^>]{1,120}>")  # strip command/XML wrappers from titles


def _title(text: str) -> str:
    """A drawer-friendly head of the opening prompt: tags out, whitespace
    collapsed, hard cap. Counted metadata, never fed to a model."""
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()[:140]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(cwd: str) -> str:
    if not cwd:
        return "?"
    return Path(cwd).name or cwd


# The home dir and the projects-encoded paths are catch-all drawers, not
# projects — they must never masquerade as an arc or inherit a vault outcome.
_MIXED = "~ mixed"


_NOTE_STOP = {"proj", "", "the", "a", "of", "and", "to", "for", "v07", "v0"}


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[-_/ .]+", s.lower()) if t and t not in _NOTE_STOP}


def _match_notes(buckets: list[str], notes: list[dict]) -> dict[str, dict]:
    """Attach vault notes to project buckets by NAME overlap, not by
    originSessionId — the note is *written* from the home dir, so its origin
    session's cwd doesn't point at the project. Name overlap is what actually
    ties `some-repo` the bucket to `proj_some_repo*` the note.

    One note serves at most ONE bucket (ISSUES #6: the per-bucket greedy match
    stamped sibling buckets with the same strongest note -> identical blurbs).
    Pairs are ranked by (overlap, specificity = overlap/|note tokens|) and
    assigned greedily; a weaker bucket falls through to its next-best note or
    to None — better a blank outcome than a confident-wrong one."""
    note_toks = []
    for n in notes:
        stem = n["file"][:-3] if n["file"].endswith(".md") else n["file"]
        note_toks.append(_tokens(stem) | _tokens(n.get("part_of") or ""))
    pairs = []
    for b in buckets:
        btoks = _tokens(b)
        if not btoks:
            continue
        need = 2 if len(btoks) >= 2 else 1
        for i, ntoks in enumerate(note_toks):
            score = len(btoks & ntoks)
            if score >= need:
                pairs.append((score, score / (len(ntoks) or 1), b, i))
    pairs.sort(key=lambda p: (-p[0], -p[1], p[2], notes[p[3]]["file"]))
    out: dict[str, dict] = {}
    taken: set[int] = set()
    for _score, _spec, b, i in pairs:
        if b in out or i in taken:
            continue
        out[b] = notes[i]
        taken.add(i)
    return out


def _longest_streak(days_sorted: list[str]) -> int:
    """Longest run of consecutive active calendar days (ISO date strings)."""
    best = run = 0
    prev = None
    for d in days_sorted:
        cur = datetime.fromisoformat(d).date()
        run = run + 1 if (prev is not None and (cur - prev).days == 1) else 1
        best = max(best, run)
        prev = cur
    return best


def _hour_phrase(h: int | None) -> str:
    if h is None:
        return "at no fixed hour"
    if h < 5:
        return "after midnight"
    if h < 9:
        return "in the early morning"
    if h < 12:
        return "through the late morning"
    if h < 17:
        return "around midday"
    if h < 21:
        return "in the evening"
    return "late at night"


def _bucket_label(cwd: str, home_name: str) -> str:
    name = _short(cwd)
    if (
        name == home_name
        or name.startswith("-home-")
        or name.startswith("-Users-")
        or name in {"?", ".claude", "projects", ""}
    ):
        return _MIXED
    return name


def _extract_text(content: object) -> tuple[str, bool]:
    """Return (text, is_tool_result). Message content is a str or a list of
    blocks; a turn made only of tool_result blocks is machine echo, not a human
    turn, and must not count as framing/push-back."""
    if isinstance(content, str):
        return content, False
    if isinstance(content, list):
        parts: list[str] = []
        saw_tool_result = False
        saw_text = False
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(str(block.get("text") or ""))
                saw_text = True
            elif btype == "tool_result":
                saw_tool_result = True
        text = "\n".join(parts)
        return text, (saw_tool_result and not saw_text)
    return "", False


class _Sess:
    __slots__ = (
        "sid", "cwd", "first", "last", "messages", "tokens_out",
        "tool_uses", "user_turns", "first_user_len", "pushbacks", "host",
        "tools", "files", "models", "tool_results", "errors", "interrupts",
        "err_streak", "err_run", "first_text", "ai_title",
    )

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.host = "local"
        self.cwd = ""
        self.first: datetime | None = None
        self.last: datetime | None = None
        self.messages = 0
        self.tokens_out = 0
        self.tool_uses = 0
        self.user_turns = 0
        self.first_user_len: int | None = None
        self.pushbacks = 0
        self.tools: Counter[str] = Counter()
        self.files: Counter[str] = Counter()
        self.models: Counter[str] = Counter()
        self.tool_results = 0
        self.errors = 0
        self.interrupts = 0
        self.err_streak = 0  # longest run of consecutive failed tool results
        self.err_run = 0
        self.first_text = ""
        self.ai_title = ""  # CLI-generated session name (ISSUES #10), beats first_text


class RecapService(BaseService):
    def __init__(self, settings: Settings, ollama: OllamaClient | None = None):
        super().__init__(settings, ttl_s=900)
        self.ollama = ollama or OllamaClient(settings.ollama_url)
        # Per-view drill indexes, keyed by (months, host). A drill request
        # names its view explicitly, so two tabs on different views no longer
        # read each other's index (the old "last computed view" trap).
        self._views: dict[tuple[int, str], dict] = {}

    def snapshot(self, months: int = 0, host: str = "all") -> RecapSnapshot:
        return self._cached(f"snapshot:{months}:{host}",
                            lambda: self._compute(months, host))

    # ------------------------------------------------------------------ walk
    def _tz(self) -> ZoneInfo | timezone:
        try:
            return ZoneInfo(self.settings.claude_usage_weekly_reset_tz)
        except (ZoneInfoNotFoundError, ValueError):
            return timezone.utc

    def _compute(self, months: int = 0, host: str = "all") -> RecapSnapshot:
        root = self.settings.claude_projects_dir
        tz = self._tz()
        cutoff: datetime | None = None
        if months > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=round(months * 30.44))
        home_name = Path.home().name
        sessions: dict[str, _Sess] = {}
        ai_titles: dict[str, str] = {}  # sid -> CLI-generated name; applied post-loop
        by_hour: Counter[int] = Counter()
        by_dow: Counter[str] = Counter()
        by_day: Counter[str] = Counter()
        # cwd bucket -> aggregates
        arc_days: dict[str, set[str]] = defaultdict(set)
        arc_sessions: dict[str, set[str]] = defaultdict(set)
        arc_first: dict[str, datetime] = {}
        arc_last: dict[str, datetime] = {}
        arc_tokens: dict[str, int] = defaultdict(int)
        topic_events: Counter[str] = Counter()
        by_dow_hour: Counter[tuple[int, int]] = Counter()
        files_parsed = 0
        host_files: Counter[str] = Counter()
        host_msgs: Counter[str] = Counter()
        host_first: dict[str, str] = {}
        host_last: dict[str, str] = {}
        bucket_hosts: dict[str, Counter[str]] = defaultdict(Counter)
        bucket_weeks: dict[str, Counter[str]] = defaultdict(Counter)
        # wider spectrum — all counted in the same single walk
        tool_mix: Counter[str] = Counter()
        model_mix: Counter[str] = Counter()
        churn_edits: Counter[str] = Counter()
        churn_sids: dict[str, set[str]] = defaultdict(set)
        by_day_host: Counter[tuple[str, str]] = Counter()

        # Multi-root walk: local projects + remote raw deltas (other host).
        # Raw files of sids already present locally are skipped; overlapping
        # lines (crash re-fetch) are dropped by event uuid below.
        local_files = list(_iter_jsonl(root)) if root.is_dir() else []
        known_sids = {p.name[:36] for p in local_files}
        files: list[tuple[Path, str]] = []
        if host in ("all", "local"):
            files += [(p, "local") for p in local_files]
        raw_dir = getattr(self.settings, "raw_dir", None)
        if host in ("all", "remote") and raw_dir and raw_dir.is_dir():
            files += [
                (p, "remote") for p in sorted(raw_dir.glob("*.jsonl"))
                if p.name[:36] not in known_sids
            ]
        if not files:
            return RecapSnapshot(generated_at=_now_iso())
        seen_uuids: set[str] = set()
        cell_days: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
        cell_sessions: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
        day_sessions: dict[str, Counter[str]] = defaultdict(Counter)
        sess_buckets: dict[str, Counter[str]] = defaultdict(Counter)

        for jsonl, origin in files:
            files_parsed += 1
            host_files[origin] += 1
            try:
                fh = jsonl.open()
            except OSError:
                continue
            with fh:
                prev_was_assistant: dict[str, bool] = {}
                for line in fh:
                    line = line.strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    dtype = d.get("type")
                    if dtype == "ai-title":
                        t = str(d.get("aiTitle") or "").strip()
                        tsid = str(d.get("sessionId") or "")
                        if t and tsid:
                            ai_titles[tsid] = t
                        continue
                    if dtype not in ("user", "assistant"):
                        continue
                    if d.get("isMeta"):
                        continue
                    uid = d.get("uuid")
                    if isinstance(uid, str):
                        if uid in seen_uuids:
                            continue
                        seen_uuids.add(uid)
                    ts = _parse_ts(d.get("timestamp"))
                    if ts is None:
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if cutoff is not None and ts < cutoff:
                        continue
                    local = ts.astimezone(tz)
                    sid = str(d.get("sessionId") or "")
                    cwd = str(d.get("cwd") or "")
                    msg = d.get("message") if isinstance(d.get("message"), dict) else {}

                    sess = sessions.get(sid)
                    if sess is None:
                        sess = sessions[sid] = _Sess(sid)
                        sess.host = origin
                    if cwd and not sess.cwd:
                        sess.cwd = cwd
                    if sess.first is None or ts < sess.first:
                        sess.first = ts
                    if sess.last is None or ts > sess.last:
                        sess.last = ts
                    sess.messages += 1

                    day = local.date().isoformat()
                    by_hour[local.hour] += 1
                    by_dow[_DOW[local.weekday()]] += 1
                    by_day[day] += 1
                    by_dow_hour[(local.weekday(), local.hour)] += 1
                    cell_days[(local.weekday(), local.hour)][day] += 1
                    host_msgs[origin] += 1
                    by_day_host[(day, origin)] += 1
                    if origin not in host_first or day < host_first[origin]:
                        host_first[origin] = day
                    if origin not in host_last or day > host_last[origin]:
                        host_last[origin] = day
                    if sid:
                        cell_sessions[(local.weekday(), local.hour)][sid] += 1
                        day_sessions[day][sid] += 1

                    bucket = _bucket_label(cwd, home_name)
                    topic_events[bucket] += 1
                    bucket_hosts[bucket][origin] += 1
                    bucket_weeks[bucket][local.strftime("%G-W%V")] += 1
                    if sid:
                        sess_buckets[sid][bucket] += 1
                    arc_days[bucket].add(day)
                    if sid:
                        arc_sessions[bucket].add(sid)
                    if bucket not in arc_first or ts < arc_first[bucket]:
                        arc_first[bucket] = ts
                    if bucket not in arc_last or ts > arc_last[bucket]:
                        arc_last[bucket] = ts

                    if dtype == "assistant":
                        content = msg.get("content")
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_use":
                                    sess.tool_uses += 1
                                    name = str(block.get("name") or "?")
                                    sess.tools[name] += 1
                                    tool_mix[name] += 1
                                    if name in _EDIT_TOOLS:
                                        inp = block.get("input")
                                        fp = inp.get("file_path") if isinstance(inp, dict) else None
                                        if fp:
                                            fname = Path(str(fp)).name
                                            sess.files[fname] += 1
                                            churn_edits[fname] += 1
                                            if sid:
                                                churn_sids[fname].add(sid)
                        mdl = str(msg.get("model") or "")
                        if mdl and not mdl.startswith("<"):
                            sess.models[mdl] += 1
                            model_mix[mdl] += 1
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            out = int(usage.get("output_tokens") or 0)
                            sess.tokens_out += out
                            arc_tokens[bucket] += out
                        prev_was_assistant[sid] = True
                    else:  # user
                        content = msg.get("content")
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "tool_result":
                                    sess.tool_results += 1
                                    if block.get("is_error"):
                                        sess.errors += 1
                                        sess.err_run += 1
                                        if sess.err_run > sess.err_streak:
                                            sess.err_streak = sess.err_run
                                    else:
                                        sess.err_run = 0
                        text, is_tool_result = _extract_text(content)
                        if not is_tool_result and text.strip():
                            sess.user_turns += 1
                            stripped = text.lstrip()
                            if stripped.startswith(_INTERRUPT_PREFIX):
                                sess.interrupts += 1
                            elif not sess.first_text and not stripped.startswith(
                                ("<command-", "<local-command")
                            ):  # slash-command echoes are not the opening ask
                                sess.first_text = _title(text)
                            if sess.first_user_len is None:
                                sess.first_user_len = len(text)
                            if prev_was_assistant.get(sid) and _PUSHBACK_RE.search(text):
                                sess.pushbacks += 1
                        prev_was_assistant[sid] = False

        # Drill-down indexes for the API, stored PER VIEW — a drill request
        # names its (months, host) and reads that view's index, so parallel
        # tabs can't cross-read. A session's bucket is its DOMINANT one (most
        # messages) — first-cwd misfiles sessions that start in the home
        # drawer and move into a project.
        bucket_of = {sid: c.most_common(1)[0][0] for sid, c in sess_buckets.items()}
        for tsid, t in ai_titles.items():
            if tsid in sessions:
                sessions[tsid].ai_title = t
        self._views[(months, host)] = {
            "sessions": sessions,
            "bucket_of": bucket_of,
            "cell_days": cell_days,
            "cell_sessions": cell_sessions,
            "day_sessions": day_sessions,
        }

        extras = {
            "tool_mix": tool_mix, "model_mix": model_mix,
            "churn_edits": churn_edits, "churn_sids": churn_sids,
            "bucket_hosts": bucket_hosts, "by_day_host": by_day_host,
        }
        return self._assemble(
            sessions, by_hour, by_dow, by_day, arc_days, arc_sessions,
            arc_first, arc_last, arc_tokens, topic_events, files_parsed,
            by_dow_hour, months=months, host=host,
            host_files=host_files, host_msgs=host_msgs,
            host_first=host_first, host_last=host_last,
            bucket_hosts=bucket_hosts, bucket_weeks=bucket_weeks,
            bucket_of=bucket_of, extras=extras,
        )

    # -------------------------------------------------------------- assemble
    def _assemble(
        self, sessions, by_hour, by_dow, by_day, arc_days, arc_sessions,
        arc_first, arc_last, arc_tokens, topic_events, files_parsed,
        by_dow_hour, months=0, host="all",
        host_files=None, host_msgs=None, host_first=None, host_last=None,
        bucket_hosts=None, bucket_weeks=None, bucket_of=None, extras=None,
    ) -> RecapSnapshot:
        host_files = host_files or Counter()
        host_msgs = host_msgs or Counter()
        host_first = host_first or {}
        host_last = host_last or {}
        bucket_hosts = bucket_hosts or {}
        bucket_weeks = bucket_weeks or {}
        bucket_of = bucket_of or {}
        extras = extras or {}
        total_messages = sum(by_day.values())
        days_sorted = sorted(by_day)
        peak_hour = max(by_hour, key=by_hour.get) if by_hour else None
        most_dow = max(by_dow, key=by_dow.get) if by_dow else None

        msg_counts = sorted(s.messages for s in sessions.values())
        top_sess = max(sessions.values(), key=lambda s: s.messages, default=None)
        stat = RecapStat(
            total_sessions=len(sessions),
            total_messages=total_messages,
            active_days=len(by_day),
            most_active_dow=most_dow,
            peak_hour=peak_hour,
            first_day=days_sorted[0] if days_sorted else None,
            last_day=days_sorted[-1] if days_sorted else None,
            longest_streak_days=_longest_streak(days_sorted),
            median_session_msgs=int(statistics.median(msg_counts)) if msg_counts else 0,
            top_session_sid=top_sess.sid if top_sess else "",
            top_session_msgs=top_sess.messages if top_sess else 0,
        )
        window_days = 0
        if days_sorted:
            d0 = datetime.fromisoformat(days_sorted[0])
            d1 = datetime.fromisoformat(days_sorted[-1])
            window_days = (d1 - d0).days + 1

        by_hour_bins = [RhythmBin(key=f"{h:02d}", count=by_hour.get(h, 0)) for h in range(24)]
        by_dow_bins = [RhythmBin(key=d, count=by_dow.get(d, 0)) for d in _DOW]
        by_day_bins = [RhythmBin(key=d, count=by_day[d]) for d in days_sorted]

        # ---- vault join: session -> note ----
        notes = self._read_vault_notes()
        note_by_session = {n["sid"]: n for n in notes if n.get("sid")}

        # ---- arcs from cwd buckets, annotated with vault ----
        arcs: list[ProjectArc] = []
        threads: set[str] = set()
        arc_note = _match_notes([b for b in arc_days if b != _MIXED], notes)
        for bucket, days in arc_days.items():
            if bucket == _MIXED:
                continue  # the catch-all drawer is not a project arc
            note = arc_note.get(bucket)
            thread = note.get("part_of") if note else None
            outcome = note["desc"][:160] if note else ""
            if thread:
                threads.add(thread)
            arcs.append(ProjectArc(
                name=bucket,
                first_day=arc_first[bucket].astimezone(self._tz()).date().isoformat()
                if bucket in arc_first else None,
                last_day=arc_last[bucket].astimezone(self._tz()).date().isoformat()
                if bucket in arc_last else None,
                active_days=len(days),
                sessions=len(arc_sessions.get(bucket, ())),
                tokens_out=arc_tokens.get(bucket, 0),
                kind="sustained" if len(days) > 2 else "burst",
                thread=thread,
                outcome=outcome,
                source="vault" if note else "log",
            ))
        arcs.sort(key=lambda a: a.tokens_out, reverse=True)
        arcs = arcs[:24]
        self._apply_fact_bank(arcs)

        # ---- topics: cwd share of messages, enriched with vault blurb ----
        topics = self._topics(
            topic_events, notes, arc_days, arc_sessions, arc_first, arc_last,
            bucket_hosts, bucket_weeks, sessions, bucket_of,
        )

        # ---- per-host coverage: the honest "what does this chip even see" ----
        host_sess: Counter[str] = Counter(s.host for s in sessions.values())
        coverage = [
            HostCoverage(
                host=h,
                files=host_files.get(h, 0),
                sessions=host_sess.get(h, 0),
                messages=host_msgs.get(h, 0),
                first_day=host_first.get(h),
                last_day=host_last.get(h),
            )
            for h in sorted(set(host_files) | set(host_sess))
        ]

        # ---- skills: structural ----
        skills = self._skills(sessions, note_by_session)

        stat_pool = self._stat_pool(
            sessions, by_day, by_hour, by_dow, days_sorted, window_days,
            topic_events,
        )

        # ---- wider spectrum: pulse / tool mix / models / churn / friction ----
        by_day_host = extras.get("by_day_host") or {}
        pulse = [
            PulseDay(
                day=d,
                local=by_day_host.get((d, "local"), 0),
                remote=by_day_host.get((d, "remote"), 0),
            )
            for d in days_sorted[-90:]  # strip caps at ~a quarter of columns
        ]
        tool_mix = [
            ToolCount(name=n, count=c)
            for n, c in (extras.get("tool_mix") or Counter()).most_common(12)
        ]
        model_mix = [
            ToolCount(name=n.removeprefix("claude-"), count=c)
            for n, c in (extras.get("model_mix") or Counter()).most_common(6)
        ]
        churn_sids = extras.get("churn_sids") or {}
        churn = [
            FileChurn(name=n, edits=c, sessions=len(churn_sids.get(n, ())))
            for n, c in (extras.get("churn_edits") or Counter()).most_common(10)
        ]
        vals = list(sessions.values())
        streaks = sorted(
            (s for s in vals if s.err_streak >= 2),
            key=lambda s: s.err_streak, reverse=True,
        )[:5]
        friction = FrictionStat(
            tool_results=sum(s.tool_results for s in vals),
            tool_errors=sum(s.errors for s in vals),
            error_sessions=sum(1 for s in vals if s.errors),
            interrupts=sum(s.interrupts for s in vals),
            corrections=sum(s.pushbacks for s in vals),
            streaks=[
                ErrStreak(sid=s.sid, length=s.err_streak,
                          bucket=bucket_of.get(s.sid, ""))
                for s in streaks
            ],
        )

        snap = RecapSnapshot(
            generated_at=_now_iso(),
            window_days=window_days,
            parsed_files=files_parsed,
            stats=stat,
            coverage=coverage,
            stat_pool=stat_pool,
            by_hour=by_hour_bins,
            by_dow=by_dow_bins,
            by_day=by_day_bins,
            rhythm_matrix=[
                [by_dow_hour.get((d, h), 0) for h in range(24)] for d in range(7)
            ],
            topics=topics,
            arcs=arcs,
            threads=sorted(threads),
            skills=skills,
            pulse=pulse,
            tool_mix=tool_mix,
            model_mix=model_mix,
            churn=churn,
            friction=friction,
        )
        self._narrate(snap, months, host)
        return snap

    def _read_vault_notes(self) -> list[dict]:
        """Parse proj_*.md frontmatter from the vault dir next to the session
        logs. Cross-host: glob <projects>/*/memory for the one holding proj_*."""
        root = self.settings.claude_projects_dir
        vault: Path | None = None
        try:
            for entry in root.iterdir():
                cand = entry / "memory"
                if cand.is_dir() and any(cand.glob("proj_*.md")):
                    vault = cand
                    break
        except OSError:
            return []
        if vault is None:
            return []
        notes: list[dict] = []
        for p in vault.glob("proj_*.md"):
            try:
                txt = p.read_text(errors="ignore")
            except OSError:
                continue
            m = re.match(r"^---\n(.*?)\n---", txt, re.S)
            if not m:
                continue
            fm: dict[str, str] = {}
            for ln in m.group(1).splitlines():
                mm = re.match(r"\s*([\w-]+):\s*(.*)", ln)
                if mm:
                    fm[mm.group(1)] = mm.group(2).strip().strip('"')
            notes.append({
                "file": p.name,
                "desc": fm.get("description", ""),
                "part_of": fm.get("part_of"),
                "sid": fm.get("originSessionId"),
            })
        return notes

    def _stat_pool(
        self, sessions, by_day, by_hour, by_dow, days_sorted, window_days,
        topic_events,
    ) -> list[StatCard]:
        """The rollable tile pool — every value COUNTED in this walk, each
        with its provenance string (invariant #1). The UI picks a daily-seeded
        subset and re-rolls on demand; the pool itself is deterministic."""
        vals = list(sessions.values())
        pool: list[StatCard] = []
        add = lambda key, label, value, src: pool.append(
            StatCard(key=key, label=label, value=str(value), src=src))

        if vals:
            depths = sorted(s.messages for s in vals)
            med = depths[len(depths) // 2]
            add("median_depth", "messages in a typical session", f"{med:,}",
                "median of per-session message counts")
            deepest = max(vals, key=lambda s: s.messages)
            add("deepest", f"deepest session ({deepest.sid[:8]})",
                f"{deepest.messages:,}",
                "largest per-session message count in this view")
            deep = sum(1 for s in vals if s.messages >= 100)
            add("deep_sessions", "sessions that ran 100+ messages", f"{deep:,}",
                "sessions with >= 100 messages, counted")
            add("tool_calls", "tool calls delegated", f"{sum(s.tool_uses for s in vals):,}",
                "tool_use blocks counted across all sessions")
            add("corrections", "course-corrections you made",
                f"{sum(s.pushbacks for s in vals):,}",
                "user turns matching push-back markers right after a reply")
            opens = [s.first_user_len for s in vals if s.first_user_len is not None]
            if opens:
                add("opener", "chars in a median opening turn",
                    f"{int(statistics.median(opens)):,}",
                    "median length of each session's first user turn")
            toks = sum(s.tokens_out for s in vals)
            if toks:
                add("tokens_out", "assistant tokens generated",
                    f"{toks / 1e6:.1f}M" if toks >= 1e6 else f"{toks:,}",
                    "output_tokens summed from usage blocks")

        if by_day:
            busiest_day, busiest_n = max(by_day.items(), key=lambda kv: kv[1])
            add("busiest_day", f"messages on {busiest_day}, your biggest day",
                f"{busiest_n:,}", "messages counted on the single busiest date")
            add("avg_day", "messages per active day",
                f"{sum(by_day.values()) // max(len(by_day), 1):,}",
                "total messages / active days")
            add("streak", "longest streak of active days",
                _longest_streak(days_sorted),
                "max run of consecutive dates with messages")
            quiet = max(window_days - len(by_day), 0)
            add("quiet_days", f"quiet days of {window_days}", quiet,
                "window days minus active days")

        total_msgs = sum(by_day.values())
        if total_msgs:
            night = sum(by_hour.get(h, 0) for h in range(0, 5))
            add("night_share", "of messages land after midnight (00–05)",
                f"{100 * night / total_msgs:.0f}%",
                "messages in hours 00-04 / total messages")
            weekend = by_dow.get("Sat", 0) + by_dow.get("Sun", 0)
            add("weekend_share", "of messages land on weekends",
                f"{100 * weekend / total_msgs:.0f}%",
                "Sat+Sun messages / total messages")
        named = sum(1 for b in topic_events if b != _MIXED)
        if named:
            add("buckets", "distinct project directories touched", named,
                "unique non-home cwd buckets counted")
        return pool

    def _topics(
        self, topic_events, notes, arc_days=None, arc_sessions=None,
        arc_first=None, arc_last=None, bucket_hosts=None, bucket_weeks=None,
        sessions=None, bucket_of=None,
    ) -> list[TopicShare]:
        arc_days = arc_days or {}
        arc_sessions = arc_sessions or {}
        arc_first = arc_first or {}
        arc_last = arc_last or {}
        bucket_hosts = bucket_hosts or {}
        bucket_weeks = bucket_weeks or {}
        tz = self._tz()

        # tools / corrections attributed to each session's dominant bucket
        btools: Counter[str] = Counter()
        bpush: Counter[str] = Counter()
        for sid, s in (sessions or {}).items():
            b = (bucket_of or {}).get(sid)
            if b:
                btools[b] += s.tool_uses
                bpush[b] += s.pushbacks

        # trailing 12 ISO weeks, oldest first — the spark's shared x-axis
        now = datetime.now(tz)
        weeks = [
            (now - timedelta(weeks=i)).strftime("%G-W%V")
            for i in range(11, -1, -1)
        ]

        total = sum(topic_events.values()) or 1
        topic_note = _match_notes([b for b in topic_events if b != _MIXED], notes)
        rows: list[TopicShare] = []
        other = 0
        for bucket, ev in topic_events.most_common():
            pct = 100.0 * ev / total
            if pct < 2.0 or len(rows) >= 8:
                other += ev
                continue
            blurb = ""
            if bucket != _MIXED:
                note = topic_note.get(bucket)
                if note and note["desc"]:
                    blurb = note["desc"][:110]
            wk = bucket_weeks.get(bucket, {})
            rows.append(TopicShare(
                label=bucket, pct=round(pct, 1), events=ev, blurb=blurb,
                sessions=len(arc_sessions.get(bucket, ())),
                active_days=len(arc_days.get(bucket, ())),
                first_day=arc_first[bucket].astimezone(tz).date().isoformat()
                if bucket in arc_first else None,
                last_day=arc_last[bucket].astimezone(tz).date().isoformat()
                if bucket in arc_last else None,
                tools=btools.get(bucket, 0),
                pushbacks=bpush.get(bucket, 0),
                host_events=dict(bucket_hosts.get(bucket, {})),
                spark=[TopicSpark(week=w, count=wk.get(w, 0)) for w in weeks],
            ))
        if other:
            rows.append(TopicShare(
                label="other", pct=round(100.0 * other / total, 1), events=other,
            ))
        return rows

    def _skills(self, sessions: dict[str, _Sess], note_by_session) -> list[SkillEvidence]:
        vals = list(sessions.values())
        tool_total = sum(s.tool_uses for s in vals)
        deleg_sessions = sum(1 for s in vals if s.tool_uses >= 3)
        pushback_total = sum(s.pushbacks for s in vals)
        pushback_sessions = sum(1 for s in vals if s.pushbacks > 0)
        opens = [s.first_user_len for s in vals if s.first_user_len is not None]
        framing = sum(1 for x in opens if x >= _FRAMING_CHARS)
        median_open = int(statistics.median(opens)) if opens else 0
        framing_pct = round(100.0 * framing / len(opens), 0) if opens else 0
        matched_notes = sum(1 for s in sessions if s in note_by_session)

        out = [
            SkillEvidence(
                skill="Delegation",
                headline="Work goes to Claude, the diagnosis stays yours.",
                detail="Tool calls run in the loop while you read each result and "
                       "steer the next step, rather than handing off blind.",
                metric=f"{tool_total:,} tool calls across {deleg_sessions} "
                       f"multi-step sessions",
            ),
            SkillEvidence(
                skill="Description",
                headline="Context arrives in layers — you frame first, then ask.",
                detail="Sessions tend to open with your own model of the problem "
                       "before the question, so Claude never has to guess the frame.",
                metric=f"{framing_pct:.0f}% of sessions open with a framing turn "
                       f"(median opener {median_open} chars)",
            ),
            SkillEvidence(
                skill="Discernment",
                headline="You catch the moment an answer drifts.",
                detail="Corrections land right after a reply — a wrong path, a bad "
                       "number, an analogy that stopped holding — and you name it.",
                metric=f"{pushback_total} course-corrections across "
                       f"{pushback_sessions} sessions",
            ),
            SkillEvidence(
                skill="Diligence",
                headline="Threads get carried to a written outcome.",
                detail="Work doesn't evaporate when the session ends — it lands as "
                       "a durable note with a state, not a loose end.",
                metric=f"{matched_notes} sessions carried into a durable vault note",
            ),
        ]
        return out

    # ----------------------------------------------------------- drill-downs
    def _view(self, months: int, host: str) -> dict:
        """Drill index for one named view; computes it if this process has
        not walked that view yet (cold API hit or evicted store)."""
        key = (months, host)
        if key not in self._views:
            self.snapshot(months, host)
        if key not in self._views:  # snapshot came from cache without a walk
            self._cache.pop(f"snapshot:{months}:{host}", None)
            self.snapshot(months, host)
        return self._views[key]

    def _session_row(self, sid: str, s: _Sess, bucket: str, tz) -> dict:
        dur = 0
        if s.first and s.last:
            dur = int((s.last - s.first).total_seconds() // 60)
        return {
            "sid": sid[:8],
            "host": s.host,
            "bucket": bucket,
            "cwd": _short(s.cwd),
            "first": s.first.astimezone(tz).strftime("%Y-%m-%d %H:%M") if s.first else "",
            "last": s.last.astimezone(tz).strftime("%Y-%m-%d %H:%M") if s.last else "",
            "duration_m": dur,
            "messages": s.messages,
            "tools": s.tool_uses,
            "pushbacks": s.pushbacks,
            "turns": s.user_turns,
            "tokens_out": s.tokens_out,
            "errors": s.errors,
            "title": s.ai_title or s.first_text,
        }

    def drill_sessions(
        self, bucket: str | None = None, limit: int = 40,
        months: int = 0, host: str = "all",
    ) -> list[dict]:
        """Sessions behind a topic/arc card (or all) for one NAMED view."""
        view = self._view(months, host)
        tz = self._tz()
        rows = []
        for sid, s in view["sessions"].items():
            b = view["bucket_of"].get(sid, "?")
            if bucket and b != bucket:
                continue
            rows.append(self._session_row(sid, s, b, tz))
        rows.sort(key=lambda r: r["messages"], reverse=True)
        return rows[:limit]

    def drill_cell(
        self, dow: int, hour: int, months: int = 0, host: str = "all",
    ) -> dict:
        """One rhythm cell (dow x hour): its dates AND its sessions, so the
        cell drawer speaks the same representation as the sessions list."""
        view = self._view(months, host)
        tz = self._tz()
        days = [
            {"day": d, "count": n}
            for d, n in sorted(
                view["cell_days"].get((dow, hour), {}).items(),
                key=lambda kv: -kv[1])
        ]
        cell_sess = view["cell_sessions"].get((dow, hour), {})
        rows = []
        for sid, n in sorted(cell_sess.items(), key=lambda kv: -kv[1])[:40]:
            s = view["sessions"].get(sid)
            if s is None:
                continue
            row = self._session_row(sid, s, view["bucket_of"].get(sid, "?"), tz)
            row["cell_messages"] = n
            rows.append(row)
        return {"days": days, "sessions": rows}

    def drill_day(
        self, day: str, months: int = 0, host: str = "all",
    ) -> list[dict]:
        """Sessions active on one date, heaviest-on-that-date first."""
        view = self._view(months, host)
        tz = self._tz()
        rows = []
        for sid, n in sorted(
            view["day_sessions"].get(day, {}).items(), key=lambda kv: -kv[1]
        )[:60]:
            s = view["sessions"].get(sid)
            if s is None:
                continue
            row = self._session_row(sid, s, view["bucket_of"].get(sid, "?"), tz)
            row["day_messages"] = n
            rows.append(row)
        return rows

    def search_sessions(
        self, q: str, limit: int = 40, months: int = 0, host: str = "all",
    ) -> list[dict]:
        """Substring match over opening prompt, bucket and sid — the widest
        cheap net over one NAMED view. Counted rows, no model."""
        needle = q.strip().lower()
        if not needle:
            return []
        view = self._view(months, host)
        tz = self._tz()
        rows = []
        for sid, s in view["sessions"].items():
            b = view["bucket_of"].get(sid, "?")
            hay = f"{s.ai_title} {s.first_text} {b} {sid}".lower()
            if needle in hay:
                rows.append(self._session_row(sid, s, b, tz))
        rows.sort(key=lambda r: r["messages"], reverse=True)
        return rows[:limit]

    def session_detail(
        self, sid_prefix: str, months: int = 0, host: str = "all",
    ) -> dict | None:
        """One session, fully counted: tool mix, files touched, friction."""
        view = self._view(months, host)
        s = next(
            (v for k, v in view["sessions"].items() if k.startswith(sid_prefix)),
            None,
        )
        if s is None:
            return None
        tz = self._tz()
        return {
            **self._session_row(s.sid, s, view["bucket_of"].get(s.sid, "?"), tz),
            "sid_full": s.sid,
            "span_min": (
                round((s.last - s.first).total_seconds() / 60)
                if s.first and s.last else 0
            ),
            "interrupts": s.interrupts,
            "err_streak": s.err_streak,
            "tool_mix": [{"name": n, "count": c} for n, c in s.tools.most_common(10)],
            "files": [{"name": n, "count": c} for n, c in s.files.most_common(10)],
            "models": [
                {"name": n.removeprefix("claude-"), "count": c}
                for n, c in s.models.most_common(4)
            ],
        }

    # -------------------------------------------------------------- narrate
    def _model(self) -> str:
        return getattr(self.settings, "atlas_model", None) or _NARRATIVE_MODEL_FALLBACK

    def _apply_fact_bank(self, arcs: list[ProjectArc]) -> None:
        """Refresh each thread's fact-bank from counted arc data and set the
        rotating gated fact on each arc. Numbers here are COUNTED, not modelled
        (invariant #1); the hard gate lives in factbank.passes_gate."""
        tz = self._tz()
        nowdt = datetime.now(tz)
        now = int(nowdt.timestamp())
        day = nowdt.timetuple().tm_yday
        bank = FactBank(self.settings.fact_bank_path)
        for arc in arcs:
            thread = arc.thread or arc.name
            bank.refresh(thread, self._fact_candidates(arc), now)
            f = bank.rotating(thread, day)
            if f:
                a = f.get("anchor") or {}
                arc.fact = f["text"]
                arc.fact_src = (
                    f"from vault note {a['note']}" if a.get("note")
                    else f"counted: {a.get('metric', 'counted')}"
                )
                arc.bank_size = bank.count(thread)
        bank.save()

    def _fact_candidates(self, arc: ProjectArc) -> list[dict]:
        """Counted candidates for one arc — each carries a real anchor so the
        gate admits it; a naive fact (no number/outcome) is never produced."""
        out: list[dict] = []
        n_d, n_s = arc.active_days, arc.sessions
        shape = "sustained across" if arc.kind == "sustained" else "a burst of"
        out.append({
            "key": f"{arc.name}:rhythm",
            "text": f"{shape} {n_d} active day{'s' if n_d != 1 else ''}, "
                    f"{n_s} session{'s' if n_s != 1 else ''}",
            "anchor": {"metric": "active_days,sessions", "value": [n_d, n_s]},
        })
        if arc.first_day and arc.last_day and arc.first_day != arc.last_day:
            out.append({
                "key": f"{arc.name}:span",
                "text": f"ran {arc.first_day} to {arc.last_day}",
                "anchor": {"metric": "span", "value": [arc.first_day, arc.last_day]},
            })
        if arc.source == "vault" and arc.outcome:
            out.append({
                "key": f"{arc.name}:outcome",
                "text": arc.outcome,
                "anchor": {"note": arc.name, "value": arc.outcome[:40]},
            })
        return out

    def _narrate(self, snap: RecapSnapshot, months: int = 0, host: str = "all") -> None:
        """Fill snap.narrative for THIS view. Cache-first; bake via the Claude
        CLI on miss; template fallback. NUMBERS are banned from the prompt —
        every figure is counted and rendered in the UI (invariant #1)."""
        model = self._model()
        prompt = self._narrative_prompt(snap, months, host)
        view = f"{months}:{host}"

        if is_claude_model(model):
            # Cache-only in the request path — the model is called ONCE, by the
            # bake pass (bin/bake.py), not per view and never on a page load.
            prose, fresh, baked_at = NarrativeCache(
                self.settings.narrative_cache_path
            ).lookup(view, prompt)
            if prose:
                snap.narrative = prose
                snap.narrative_model = model
                snap.narrative_fallback = False
                snap.narrative_stale = not fresh
                snap.narrative_baked_at = baked_at
                return
        else:
            try:
                raw = self.ollama.generate(
                    model=model,
                    prompt=prompt,
                    timeout_s=max(60, self.settings.atlas_ollama_timeout_s),
                    temperature=0.7,
                    num_predict=360,
                )
                text = raw.strip()
                if text:
                    snap.narrative = text
                    snap.narrative_model = model
                    snap.narrative_fallback = False
                    return
            except (OllamaError, ValueError):
                pass

        snap.narrative_model = "template"
        snap.narrative = self._narrative_fallback(snap)
        snap.narrative_fallback = True

    _PERIOD_PHRASE = {
        0: "across all their logged sessions",
        1: "over the past month",
        3: "over the past three months",
        6: "over the past six months",
        12: "over the past year",
    }
    _HOST_PHRASE = {
        "all": "across both machines",
        "local": "on their local host workstation",
        "remote": "on their remote host",
    }

    # Single-view header (also the cache-key text — keep byte-stable or every
    # baked view goes cold). The batch bake uses its own multi-view header.
    _NARR_HEADER = (
        "You are writing the opening paragraph of a personal 'Reflect' recap "
        "of a developer's time with an AI coding agent. 3-4 sentences, second "
        "person, warm but precise, no hype, no lists. Output ONLY the "
        "paragraph — no preamble, no heading.\n"
        "IMPORTANT: do NOT state any exact numbers, counts, or percentages — "
        "those are shown next to this paragraph. Narrate the SHAPE and the "
        "THREADS.\n\n"
    )

    def _narrative_shape(self, snap: RecapSnapshot, months: int, host: str) -> str:
        """The view-specific QUALITATIVE shape — no numbers (the model fabricates
        any count it is handed; the real figures already render in the tiles)."""
        top_arcs = [a for a in snap.arcs if a.source == "vault"][:6] or snap.arcs[:6]
        arc_lines = "\n".join(
            f"- {a.name} ({a.kind}): {a.outcome or 'in-flight'}" for a in top_arcs
        )
        dow = snap.stats.most_active_dow or "no particular day"
        period = self._PERIOD_PHRASE.get(months, f"over the past {months} months")
        hostp = self._HOST_PHRASE.get(host, host)
        return (
            f"Shape: near-daily sessions {period} {hostp}; rhythm peaks "
            f"{_hour_phrase(snap.stats.peak_hour)}, heaviest on {dow}; work split "
            f"between a large uncategorised mix and a few focused threads.\n"
            f"Threads:\n{arc_lines}\n"
        )

    def _narrative_prompt(self, snap: RecapSnapshot, months: int, host: str) -> str:
        """Single-view prompt = cache key. Output is byte-stable across the
        split so already-baked entries keep matching."""
        return self._NARR_HEADER + self._narrative_shape(snap, months, host)

    def _narrative_fallback(self, snap: RecapSnapshot) -> str:
        top = ", ".join(t.label for t in snap.topics[:3]) or "a handful of threads"
        return (
            f"Over {snap.window_days} days you ran {snap.stats.total_sessions} "
            f"sessions, most alive around {snap.stats.peak_hour}:00 and heaviest on "
            f"{snap.stats.most_active_dow}. The work clustered in {top} — "
            f"{len(snap.threads)} of it carried far enough to leave a named thread "
            f"behind. The shape is less a scatter of tasks than a few arcs you kept "
            f"returning to."
        )
