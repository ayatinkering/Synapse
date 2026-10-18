"""Versioned public contracts for the offline research pipeline."""

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LABEL: Literal["Offline fixture demonstration"] = "Offline fixture demonstration"
Text = Annotated[str, Field(min_length=1, max_length=1000)]


def now() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1


class State(StrEnum):
    QUEUED = "queued"
    DISCOVERING = "discovering"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    CRITIQUING = "critiquing"
    SOURCES_READY = "sources_ready"
    REPORT_READY = "report_ready"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INSUFFICIENT = "insufficient_evidence"


TERMINAL = {
    State.COMPLETED,
    State.FAILED,
    State.CANCELLED,
    State.INSUFFICIENT,
    State.SOURCES_READY,
    State.REPORT_READY,
}


class RunInput(Model):
    topic: Text
    question: Text
    subquestions: list[Text] = Field(default_factory=list, max_length=3)
    date_preference: str | None = None

    @field_validator("subquestions")
    @classmethod
    def clean_subquestions(cls, values: list[str]) -> list[str]:
        if any(not v.strip() for v in values):
            raise ValueError("Subquestions must contain text")
        return [v.strip() for v in values]

    @field_validator("topic", "question")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Input must contain non-whitespace text")
        return value.strip()


class Limits(Model):
    max_queries: int = Field(default=3, ge=1)
    results_per_query: int = Field(default=5, ge=1)
    max_sources: int = Field(default=10, ge=1)
    text_characters: int = Field(default=3000, ge=1)
    deadline_seconds: float = Field(default=600, gt=0, allow_inf_nan=False)
    fetch_timeout_seconds: int = Field(default=15, gt=0)
    response_bytes: int = Field(default=2_000_000, gt=0)
    transient_retries: int = Field(default=2, ge=0, le=2)


class SynthesisConfig(Model):
    model: str = Field(default="gemini-3.5-flash-lite", pattern=r"^gemini-[a-z0-9.-]+$")
    max_input_tokens: int = Field(default=8192, ge=1, le=100_000)
    max_output_tokens: int = Field(default=2048, ge=128, le=8192)
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class SynthesisRecord(Model):
    status: Literal["started", "counted", "generating", "generated", "validated"]
    counted_input_tokens: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    thinking_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    model_version: str | None = None


class Run(Model):
    id: UUID = Field(default_factory=uuid4)
    fixture_id: str | None = None
    kind: Literal["fixture", "live"] = "fixture"
    synthesis_config: SynthesisConfig | None = None
    critique_config: SynthesisConfig | None = None
    critique_key: str | None = None
    input: RunInput
    state: State = State.QUEUED
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    limits: Limits = Field(default_factory=Limits)
    model_id: str | None = "fixture-v1"
    prompt_version: str | None = "fixture-v1"
    cancel_requested: bool = False
    error: str | None = None
    label: Literal[
        "Offline fixture demonstration",
        "Live discovery — report pending",
        "Gemini synthesis — critique pending",
        "Live research",
    ] = LABEL


class Attempt(Model):
    number: int = Field(ge=1, le=3)
    status: Literal["started", "success", "failed"]
    error: str | None = None
    status_code: int | None = None
    request_id: str | None = Field(default=None, max_length=200)
    credits: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class DiscoveryPreview(Model):
    input: RunInput
    queries: list[str]
    date_preference: Literal["day", "week", "month", "year"] | None
    limits: Limits


class Query(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    text: Text
    provider: str = "bundled-fixture"
    requested_date_filter: str | None = None
    status: Literal["pending", "success", "failed"] = "success"
    error: str | None = None
    attempts: list[Attempt] = Field(default_factory=list)


class SearchHit(Model):
    query_id: UUID
    rank: int = Field(ge=1)
    score: float | None = Field(default=None, allow_inf_nan=False)
    snippet: str = Field(default="", max_length=1000)


class Candidate(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    query_ids: list[UUID]
    url: str
    title: str
    relevance: str
    search_hits: list[SearchHit] = Field(default_factory=list)


class Discovery(Model):
    run_id: UUID
    queries: list[Query]
    candidates: list[Candidate]


class Source(Model):
    id: UUID
    run_id: UUID
    query_ids: list[UUID]
    display_id: str = Field(pattern=r"^S[0-9]{2,}$")
    original_url: str
    final_url: str
    title: str
    retrieved_at: datetime = Field(default_factory=now)
    published_at: datetime | None = None
    extracted_text: str
    content_hash: str
    truncated: bool
    status: Literal["fetched", "failed"]
    error: str | None = None
    label: Literal["Offline fixture demonstration", "Live discovery — report pending"] = LABEL

    @model_validator(mode="after")
    def hash_matches(self) -> "Source":
        if sha256(self.extracted_text.encode()).hexdigest() != self.content_hash:
            raise ValueError("Source hash does not match stored cleaned text")
        return self


class Evidence(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    source_id: UUID
    display_id: str = Field(pattern=r"^E[0-9]{2,}$")
    excerpt: str = Field(min_length=1)
    excerpt_start: int = Field(ge=0)
    excerpt_end: int = Field(gt=0)
    relevance_note: str
    limitations: str = "Synthetic example; not research evidence."


class Analysis(Model):
    run_id: UUID
    sources: list[Source]
    evidence: list[Evidence]


class Claim(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    display_id: str = Field(pattern=r"^C[0-9]{2,}$")
    text: str
    evidence_ids: list[UUID]
    requires_evidence: bool = True
    section: Literal["Findings", "Comparison", "Conclusion"] = "Findings"
    support_status: Literal["cited", "interpretation"] = "cited"
    quote: str | None = None


class Section(Model):
    title: str
    text: str


class Report(Model):
    run_id: UUID
    version: Literal[1] = 1
    sections: list[Section]
    claims: list[Claim]
    validation_results: list[str] = Field(default_factory=list)
    label: Literal["Offline fixture demonstration", "Generated report — critique pending"] = LABEL


class Finding(Model):
    claim_id: UUID
    comment: str


class Critique(Model):
    run_id: UUID
    report_version: Literal[1] = 1
    scores: list[Annotated[int, Field(strict=True, ge=0, le=2)]] = Field(min_length=5, max_length=5)
    findings: list[Finding]
    total: int = Field(strict=True, ge=0, le=10)
    evaluator_model: str = "fixture-v1 (predetermined, not a model evaluation)"
    prompt_version: str = "fixture-v1"
    label: Literal["Offline fixture demonstration", "Model critique — not a fact check"] = LABEL

    @model_validator(mode="after")
    def valid_total(self) -> "Critique":
        if self.total != sum(self.scores):
            raise ValueError("Critique total must equal the five scores")
        return self


class Event(Model):
    run_id: UUID
    sequence: int
    stage: State
    type: str
    timestamp: datetime = Field(default_factory=now)
    duration_seconds: float = 0
    message: str


class Snapshot(Model):
    schema_version: Literal[1] = 1
    run: Run
    discovery: Discovery | None = None
    analysis: Analysis | None = None
    report: Report | None = None
    critique: Critique | None = None
    synthesis: SynthesisRecord | None = None
    critique_usage: SynthesisRecord | None = None
    events: list[Event] = Field(default_factory=list)


class FixtureInfo(Model):
    id: str
    name: str
    input: RunInput
    queries: list[str]
    label: Literal["Offline fixture demonstration"] = LABEL
