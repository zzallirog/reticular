from __future__ import annotations

from pydantic import BaseModel, Field


class RecapStat(BaseModel):
    """Headline numbers — the three tiles at the top of the Reflect card."""
    total_sessions: int = 0
    total_messages: int = 0
    active_days: int = 0
    most_active_dow: str | None = None
    peak_hour: int | None = None
    first_day: str | None = None
    last_day: str | None = None
    longest_streak_days: int = 0
    median_session_msgs: int = 0
    top_session_sid: str = ""  # deepest session (most messages) — drillable
    top_session_msgs: int = 0


class RhythmBin(BaseModel):
    key: str
    count: int


class HostCoverage(BaseModel):
    """What one host's data actually covers in this view — the honest answer
    to "why does the remote chip show so little": the remote side is collector
    deltas, and this row says exactly how many files and since when."""
    host: str
    files: int = 0
    sessions: int = 0
    messages: int = 0
    first_day: str | None = None
    last_day: str | None = None


class StatCard(BaseModel):
    """One counted stat for the rollable tile pool. `src` is provenance for
    the verified-number tooltip; every value here is counted, never modelled."""
    key: str
    label: str
    value: str
    src: str


class TopicSpark(BaseModel):
    """One bar of a topic's activity trend — messages counted per ISO week."""
    week: str
    count: int


class TopicShare(BaseModel):
    """One row of "What you spent time on" — derived from cwd buckets, enriched
    with a vault blurb when a project note matches."""
    label: str
    pct: float
    events: int
    blurb: str = ""
    sessions: int = 0
    active_days: int = 0
    first_day: str | None = None
    last_day: str | None = None
    tools: int = 0
    pushbacks: int = 0
    host_events: dict[str, int] = Field(default_factory=dict)  # same events, split by host
    spark: list[TopicSpark] = Field(default_factory=list)


class ToolCount(BaseModel):
    """One counted name→count pair (tool mix, model mix)."""
    name: str
    count: int


class PulseDay(BaseModel):
    """One day of the pulse strip, host-split. Counted messages."""
    day: str
    local: int = 0
    remote: int = 0


class FileChurn(BaseModel):
    """Edit/Write concentration on one file across the view — effort signal."""
    name: str
    edits: int
    sessions: int


class ErrStreak(BaseModel):
    """Longest run of consecutive failed tool results inside one session."""
    sid: str
    length: int
    bucket: str = ""


class FrictionStat(BaseModel):
    """Where it hurt — counted friction, never modelled."""
    tool_results: int = 0
    tool_errors: int = 0
    error_sessions: int = 0
    interrupts: int = 0
    corrections: int = 0
    streaks: list[ErrStreak] = Field(default_factory=list)


class ProjectArc(BaseModel):
    """A project's life as seen from the logs, annotated with vault meaning.

    `kind` is "burst" (<= 2 active days) or "sustained". `thread` is the vault
    `part_of` grouping (fixes cwd fragmentation — three repo buckets, one arc).
    `outcome`/`source` come from the matched proj_*.md note when present."""
    name: str
    first_day: str | None = None
    last_day: str | None = None
    active_days: int = 0
    sessions: int = 0
    tokens_out: int = 0
    kind: str = "burst"
    thread: str | None = None
    outcome: str = ""
    source: str = "log"  # "log" | "vault"
    fact: str = ""  # rotating gated fact from the fact-bank (Pass 3)
    fact_src: str = ""  # provenance for the fact's counted anchor
    bank_size: int = 0  # facts held for this thread (bank is larger than shown)


class SkillEvidence(BaseModel):
    """One AI-fluency skill, grounded in a structural metric — NOT an LLM guess.

    Delegation / Description / Discernment / Diligence, each with the number
    that earns the claim so it can't drift into flattery."""
    skill: str
    headline: str
    detail: str
    metric: str = ""


class RecapSnapshot(BaseModel):
    schema_version: int = 1
    generated_at: str
    window_days: int = 0
    parsed_files: int = 0
    stats: RecapStat = Field(default_factory=RecapStat)
    by_hour: list[RhythmBin] = Field(default_factory=list)
    by_dow: list[RhythmBin] = Field(default_factory=list)
    by_day: list[RhythmBin] = Field(default_factory=list)
    rhythm_matrix: list[list[int]] = Field(
        default_factory=list, description="7 rows (Mon..Sun) x 24 hour counts"
    )
    topics: list[TopicShare] = Field(default_factory=list)
    coverage: list[HostCoverage] = Field(
        default_factory=list, description="per-host data coverage in this view"
    )
    stat_pool: list[StatCard] = Field(
        default_factory=list, description="counted stats for the rollable tiles"
    )
    arcs: list[ProjectArc] = Field(default_factory=list)
    threads: list[str] = Field(default_factory=list)
    skills: list[SkillEvidence] = Field(default_factory=list)
    pulse: list[PulseDay] = Field(default_factory=list)
    tool_mix: list[ToolCount] = Field(default_factory=list)
    model_mix: list[ToolCount] = Field(default_factory=list)
    churn: list[FileChurn] = Field(default_factory=list)
    friction: FrictionStat = Field(default_factory=FrictionStat)
    narrative: str = ""
    narrative_model: str = ""
    narrative_fallback: bool = False
    narrative_stale: bool = False  # prose served past its bake (shape drifted)
    narrative_baked_at: int | None = None  # unix secs of the serving prose's bake
