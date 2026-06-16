from datetime import UTC, datetime
from uuid import uuid4

import pytest
from neroops.models import EntryType
from neroops.schemas import EntryCreate, validate_payload
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("entry_type", "payload"),
    [
        (EntryType.feeding, {"food": "Корм", "amount": 250, "unit": "g", "appetite": 5}),
        (EntryType.walk, {"duration_minutes": 45, "distance_km": 2.3, "quality": 4}),
        (EntryType.symptom, {"category": "reflux", "severity": 2, "count": 1}),
        (
            EntryType.wellbeing,
            {"appetite": 5, "energy": 4, "mood": 5, "sleep": 4, "pain": 1},
        ),
        (
            EntryType.training,
            {"duration_minutes": 15, "commands": ["рядом", "ко мне"], "engagement": 4},
        ),
        (EntryType.medication, {"name": "Препарат", "dose": 1.5, "unit": "tablet"}),
        (EntryType.weight, {"weight_kg": 32.4}),
        (EntryType.vet_visit, {"reason": "Плановый осмотр"}),
        (EntryType.note, {"title": "Хороший день"}),
    ],
)
def test_payloads_accept_valid_data(entry_type: EntryType, payload: dict) -> None:
    assert validate_payload(entry_type, payload)


def test_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        validate_payload(EntryType.weight, {"weight_kg": 32, "mystery": True})


def test_payload_rejects_score_outside_scale() -> None:
    with pytest.raises(ValidationError):
        validate_payload(
            EntryType.wellbeing,
            {"appetite": 6, "energy": 4, "mood": 4},
        )


def test_entry_normalizes_payload() -> None:
    entry = EntryCreate(
        id=uuid4(),
        pet_id=uuid4(),
        type=EntryType.training,
        occurred_at=datetime.now(UTC),
        payload={"duration_minutes": 10, "commands": [" рядом ", "", "место"]},
    )
    assert entry.payload["commands"] == ["рядом", "место"]
