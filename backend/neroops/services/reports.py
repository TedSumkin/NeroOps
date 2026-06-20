from collections import Counter, defaultdict
from datetime import date
from statistics import mean
from zoneinfo import ZoneInfo

from neroops.models import Entry, EntryType
from neroops.schemas import DailyCount, SummaryResponse


def build_summary(
    entries: list[Entry],
    from_date: date,
    to_date: date,
    timezone_name: str = "Europe/Moscow",
) -> SummaryResponse:
    """Build an aggregate report for already selected diary entries.

    The function is intentionally independent from FastAPI and SQLAlchemy
    queries: callers are responsible for selecting the pet and filtering entries
    to the requested period before calling it.

    Args:
        entries: Entries to aggregate. Their ``occurred_at`` values should be
            timezone-aware datetimes.
        from_date: Inclusive report start date shown in the response.
        to_date: Inclusive report end date shown in the response.
        timezone_name: IANA timezone name used to group entries by local day.

    Returns:
        ``SummaryResponse`` with entry counts by type, symptom episode counts,
        average score fields, weight history, and per-day entry counts.
    """
    counts_by_type = Counter(entry.type.value for entry in entries)
    symptom_counts: Counter[str] = Counter()
    score_values: dict[str, list[float]] = defaultdict(list)
    daily_counts: Counter[date] = Counter()
    weight_series: list[dict[str, str | float]] = []

    for entry in entries:
        payload = entry.payload or {}
        local_occurred_at = entry.occurred_at.astimezone(ZoneInfo(timezone_name))
        daily_counts[local_occurred_at.date()] += 1

        if entry.type == EntryType.symptom:
            symptom_counts[str(payload.get("category", "other"))] += int(payload.get("count", 1))

        if entry.type == EntryType.weight and "weight_kg" in payload:
            weight_series.append(
                {
                    "occurred_at": entry.occurred_at.isoformat(),
                    "weight_kg": float(payload["weight_kg"]),
                }
            )

        for key in ("appetite", "energy", "mood", "sleep", "pain", "quality", "engagement"):
            value = payload.get(key)
            if isinstance(value, int | float):
                score_values[key].append(float(value))

    return SummaryResponse(
        from_date=from_date,
        to_date=to_date,
        total_entries=len(entries),
        counts_by_type=dict(counts_by_type),
        symptom_counts=dict(symptom_counts),
        average_scores={key: round(mean(values), 2) for key, values in score_values.items()},
        weight_series=sorted(weight_series, key=lambda item: str(item["occurred_at"])),
        daily_counts=[
            DailyCount(date=day, count=count) for day, count in sorted(daily_counts.items())
        ],
    )
