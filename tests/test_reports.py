from datetime import UTC, date, datetime

from neroops.models import Entry, EntryType
from neroops.services.reports import build_summary


def make_entry(entry_type: EntryType, payload: dict, occurred_at: datetime) -> Entry:
    return Entry(
        id="entry-id",
        pet_id="pet-id",
        type=entry_type,
        occurred_at=occurred_at,
        payload=payload,
    )


def test_summary_aggregates_symptoms_scores_and_weight() -> None:
    entries = [
        make_entry(
            EntryType.symptom,
            {"category": "reflux", "severity": 3, "count": 2},
            datetime(2026, 6, 14, 20, tzinfo=UTC),
        ),
        make_entry(
            EntryType.wellbeing,
            {"appetite": 5, "energy": 3, "mood": 4},
            datetime(2026, 6, 14, 21, tzinfo=UTC),
        ),
        make_entry(
            EntryType.weight,
            {"weight_kg": 32.5},
            datetime(2026, 6, 13, 8, tzinfo=UTC),
        ),
    ]

    summary = build_summary(
        entries,
        date(2026, 6, 13),
        date(2026, 6, 15),
        "Europe/Moscow",
    )

    assert summary.total_entries == 3
    assert summary.counts_by_type["symptom"] == 1
    assert summary.symptom_counts == {"reflux": 2}
    assert summary.average_scores["appetite"] == 5
    assert summary.weight_series[0]["weight_kg"] == 32.5
    assert summary.daily_counts[-1].date == date(2026, 6, 15)
