from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from neroops.models import EntryType

Score = Annotated[int, Field(ge=1, le=5)]
PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeedingPayload(StrictPayload):
    food: str = Field(min_length=1, max_length=200)
    amount: PositiveFloat | None = None
    unit: Literal["g", "kg", "ml", "portion", "piece"] | None = None
    appetite: Score | None = None
    reaction: str | None = Field(default=None, max_length=500)


class WalkPayload(StrictPayload):
    duration_minutes: Annotated[int, Field(gt=0, le=1440)]
    distance_km: NonNegativeFloat | None = None
    energy: Score | None = None
    quality: Score | None = None


class SymptomPayload(StrictPayload):
    category: Literal[
        "digestion",
        "stool",
        "vomiting",
        "reflux",
        "gas",
        "pain",
        "limping",
        "skin",
        "breathing",
        "other",
    ]
    severity: Score
    count: Annotated[int, Field(ge=1, le=100)] = 1
    body_area: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class WellbeingPayload(StrictPayload):
    appetite: Score
    energy: Score
    mood: Score
    sleep: Score | None = None
    pain: Score | None = None


class TrainingPayload(StrictPayload):
    duration_minutes: Annotated[int, Field(gt=0, le=1440)]
    commands: list[str] = Field(default_factory=list, max_length=30)
    engagement: Score | None = None
    result: str | None = Field(default=None, max_length=500)

    @field_validator("commands")
    @classmethod
    def normalize_commands(cls, commands: list[str]) -> list[str]:
        return [command.strip() for command in commands if command.strip()]


class MedicationPayload(StrictPayload):
    name: str = Field(min_length=1, max_length=200)
    dose: PositiveFloat
    unit: Literal["mg", "ml", "tablet", "capsule", "drop", "dose"]


class WeightPayload(StrictPayload):
    weight_kg: Annotated[float, Field(gt=0, le=200)]


class VetVisitPayload(StrictPayload):
    reason: str = Field(min_length=1, max_length=1000)
    diagnosis: str | None = Field(default=None, max_length=2000)
    recommendations: str | None = Field(default=None, max_length=4000)
    follow_up_date: date | None = None


class NotePayload(StrictPayload):
    title: str | None = Field(default=None, max_length=200)


PAYLOAD_MODELS: dict[EntryType, type[StrictPayload]] = {
    EntryType.feeding: FeedingPayload,
    EntryType.walk: WalkPayload,
    EntryType.symptom: SymptomPayload,
    EntryType.wellbeing: WellbeingPayload,
    EntryType.training: TrainingPayload,
    EntryType.medication: MedicationPayload,
    EntryType.weight: WeightPayload,
    EntryType.vet_visit: VetVisitPayload,
    EntryType.note: NotePayload,
}


def validate_payload(entry_type: EntryType, payload: dict[str, Any]) -> dict[str, Any]:
    model = PAYLOAD_MODELS[entry_type]
    return TypeAdapter(model).validate_python(payload).model_dump(mode="json")


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    species: str
    breed: str | None
    birth_date: date | None


class PetUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    species: str = Field(default="dog", min_length=1, max_length=50)
    breed: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    url: str | None = None

    @model_validator(mode="after")
    def add_url(self) -> "AttachmentRead":
        self.url = f"/api/v1/attachments/{self.id}"
        return self


class EntryBase(BaseModel):
    id: UUID
    pet_id: UUID
    type: EntryType
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_payload(self) -> "EntryBase":
        self.payload = validate_payload(self.type, self.payload)
        return self


class EntryCreate(EntryBase):
    pass


class EntryUpdate(BaseModel):
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] | None = None


class EntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pet_id: str
    type: EntryType
    occurred_at: datetime
    note: str | None
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    attachments: list[AttachmentRead] = Field(default_factory=list)


class EntryPage(BaseModel):
    items: list[EntryRead]
    total: int
    limit: int
    offset: int


class CatalogItem(BaseModel):
    value: str
    label: str


class BootstrapResponse(BaseModel):
    pet: PetRead
    entry_types: list[CatalogItem]
    recent_entries: list[EntryRead]
    server_time: datetime


class DailyCount(BaseModel):
    date: date
    count: int


class SummaryResponse(BaseModel):
    from_date: date
    to_date: date
    total_entries: int
    counts_by_type: dict[str, int]
    symptom_counts: dict[str, int]
    average_scores: dict[str, float]
    weight_series: list[dict[str, str | float]]
    daily_counts: list[DailyCount]
