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
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INSUFFICIENT = "insufficient_evidence"


TERMINAL = {State.COMPLETED, State.FAILED, State.CANCELLED, State.INSUFFICIENT}


class RunInput(Model):
    topic: Text
    question: Text
    subquestions: list[Text] = Field(default_factory=list, max_length=3)
    date_preference: str | None = None

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
    deadline_seconds: float = Field(default=600, gt=0)
    fetch_timeout_seconds: int = 15
    response_bytes: int = 2_000_000
    transient_retries: int = 2


class Run(Model):
    id: UUID = Field(default_factory=uuid4)
    fixture_id: str
    input: RunInput
    state: State = State.QUEUED
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    limits: Limits = Field(default_factory=Limits)
    model_id: str = "fixture-v1"
    prompt_version: str = "fixture-v1"
    cancel_requested: bool = False
    error: str | None = None
    label: Literal["Offline fixture demonstration"] = LABEL


class Query(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    text: Text
    provider: str = "bundled-fixture"
    requested_date_filter: str | None = None


class Candidate(Model):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    query_ids: list[UUID]
    url: str
    title: str
    relevance: str


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
    label: Literal["Offline fixture demonstration"] = LABEL

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
    label: Literal["Offline fixture demonstration"] = LABEL


class Finding(Model):
    claim_id: UUID
    comment: str


class Critique(Model):
    run_id: UUID
    report_version: Literal[1] = 1
    scores: list[Annotated[int, Field(strict=True, ge=0, le=2)]] = Field(min_length=5, max_length=5)
    findings: list[Finding]
    total: int = Field(ge=0, le=10)
    evaluator_model: str = "fixture-v1 (predetermined, not a model evaluation)"
    prompt_version: str = "fixture-v1"
    label: Literal["Offline fixture demonstration"] = LABEL

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
    events: list[Event] = Field(default_factory=list)


class FixtureInfo(Model):
    id: str
    name: str
    input: RunInput
    queries: list[str]
    label: Literal["Offline fixture demonstration"] = LABEL
