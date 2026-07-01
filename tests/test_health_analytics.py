"""This file contains tests for health-analytics related classes and methods"""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from neroops.models import Entry, EntryType
from neroops.services.health_analytics import (
    count_state_statistics,
    count_symptom_free_days,
    symptom_count,
    symptom_frequency,
)


def make_entry(
    entry_type: EntryType, occurred_at: datetime, payload: dict | None = None
):
    return Entry(
        id=f"{entry_type.value}-{occurred_at.isoformat()}",
        pet_id="pet-id",
        type=entry_type,
        occurred_at=occurred_at,
        payload=payload or {},
    )


def date_to_datetime(this_date: date, zone_info=None) -> datetime:
    return datetime(this_date.year, this_date.month, this_date.day, tzinfo=zone_info)


@pytest.fixture()
def dates_essentials() -> tuple[date, date, ZoneInfo]:
    year = 2026
    month = 1
    start = 8
    end = 8 + 6
    from_date = date(year, month, start)
    to_date = date(year, month, end)
    zone_info = ZoneInfo("Europe/Moscow")
    return (from_date, to_date, zone_info)


@pytest.fixture()
def entrylist_and_datetimes(
    dates_essentials,
) -> tuple[date, date, ZoneInfo, list[EntryType]]:
    from_date, to_date, zone_info = dates_essentials

    year = from_date.year
    month = from_date.month
    start_day = from_date.day
    to_date = from_date + timedelta(days=5)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=start_day, hour=12, tzinfo=zone_info),
            payload={
                "category": "vomitting",
                "severity": 1,
                "count": 2,
                "body_area": None,
                "description": "не туда, семпай",
            },
        ),
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=start_day + 1, hour=12, tzinfo=zone_info
            ),
            payload={
                "category": "gas",
                "severity": 1,
                "count": 2,
                "body_area": None,
                "description": "не туда, семпай",
            },
        ),
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=start_day + 2, hour=12, tzinfo=zone_info
            ),
            payload={
                "category": "limping",
                "severity": 1,
                "count": 3,
                "body_area": None,
                "description": "туда, семпай",
            },
        ),
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=start_day + 3, hour=14, tzinfo=zone_info
            ),
            payload={
                "category": "skin",
                "severity": 1,
                "count": 1,
                "body_area": None,
                "description": "туда, семпай, покраснение кожи",
            },
        ),
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=start_day + 4, hour=14, tzinfo=zone_info
            ),
            payload={
                "category": "reflux",
                "severity": 1,
                "count": 1,
                "body_area": None,
                "description": "туда, семпай",
            },
        ),
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=start_day + 5, hour=14, tzinfo=zone_info
            ),
            payload={
                "category": "ears",
                "severity": 1,
                "count": 1,
                "body_area": None,
                "description": "не туда, семпай",
            },
        ),
    ]
    return (from_date, to_date, zone_info, entries)


@pytest.fixture()
def empty_entry_list_fixture(dates_essentials):
    from_date, to_date, zone_info = dates_essentials
    entries = []
    return (from_date, to_date, zone_info, entries)


@pytest.fixture()
def empty_count_statistics_result():
    none_stats = {"mean": None, "std": None, "min": None, "max": None}
    expected_result = {
        "appetite": none_stats.copy(),
        "energy": none_stats.copy(),
        "mood": none_stats.copy(),
        "sleep": none_stats.copy(),
        "pain": none_stats.copy(),
        "quality": none_stats.copy(),
        "engagement": none_stats.copy(),
    }
    return expected_result


@pytest.fixture()
def inverse_period_dates_essentials(dates_essentials):
    from_date, to_date, zone_info = dates_essentials
    from_date, to_date = to_date, from_date
    return from_date, to_date, zone_info


def _entry_at(
    entry_type: EntryType,
    occurred_on: date,
    tz: timezone | ZoneInfo,
    payload: dict | None = None,
    *,
    hour: int = 0,
    minute: int = 0,
) -> Entry:
    return make_entry(
        entry_type,
        datetime(
            occurred_on.year,
            occurred_on.month,
            occurred_on.day,
            hour,
            minute,
            tzinfo=tz,
        ),
        payload=payload,
    )


def _all_entry_type_examples(occurred_on: date, tz: timezone | ZoneInfo) -> list[Entry]:
    return [
        _entry_at(
            EntryType.symptom,
            occurred_on,
            tz,
            {"category": "skin", "severity": 1, "count": 1},
        ),
        _entry_at(
            EntryType.feeding,
            occurred_on,
            tz,
            {"food": "royal canin", "amount": 200, "unit": "g", "appetite": 5},
            hour=1,
        ),
        _entry_at(
            EntryType.walk,
            occurred_on,
            tz,
            {"duration_minutes": 20, "distance_km": 0.6, "energy": 5, "quality": 5},
            hour=2,
        ),
        _entry_at(
            EntryType.wellbeing,
            occurred_on,
            tz,
            {"appetite": 4, "energy": 4, "mood": 5, "sleep": 5, "pain": 1},
            hour=3,
        ),
        _entry_at(
            EntryType.training,
            occurred_on,
            tz,
            {"duration_minutes": 15, "commands": ["sit"], "engagement": 3},
            hour=4,
        ),
        _entry_at(
            EntryType.medication,
            occurred_on,
            tz,
            {"name": "enterosgel", "dose": 1, "unit": "mg"},
            hour=5,
        ),
        _entry_at(EntryType.weight, occurred_on, tz, {"weight_kg": 40}, hour=6),
        _entry_at(
            EntryType.vet_visit,
            occurred_on,
            tz,
            {"reason": "skin", "diagnosis": "reflux"},
            hour=7,
        ),
        _entry_at(EntryType.note, occurred_on, tz, {"title": "note"}, hour=8),
    ]


def test_count_symptom_free_days_deterministic(entrylist_and_datetimes):
    from_date, to_date, tz, entries = entrylist_and_datetimes

    output_1 = count_symptom_free_days(entries, from_date, to_date, tz)
    output_2 = count_symptom_free_days(entries, from_date, to_date, tz)

    assert output_1 == output_2


def test_count_symptom_free_days_handles_empty_entry_lists(empty_entry_list_fixture):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    output = count_symptom_free_days(entries, from_date, to_date, tz)
    period_days = (to_date - from_date).days + 1

    assert output == period_days


def test_count_symptom_free_days_handles_multiple_entries_in_one_day(dates_essentials):
    from_date, to_date, tz = dates_essentials
    middle_day = from_date + (to_date - from_date) // 2
    entry_list = [
        _entry_at(
            EntryType.symptom,
            middle_day,
            tz,
            {"category": "cough", "count": 1},
            hour=13,
        ),
        _entry_at(
            EntryType.symptom,
            middle_day,
            tz,
            {"category": "cough", "count": 1},
            hour=13,
            minute=1,
        ),
    ]
    entry_list_2nd = deepcopy(entry_list) + [
        _entry_at(
            EntryType.symptom,
            middle_day,
            tz,
            {"category": "cough", "count": 1},
            hour=20,
        )
    ]
    output = count_symptom_free_days(entry_list, from_date, to_date, tz)
    output_2nd = count_symptom_free_days(entry_list_2nd, from_date, to_date, tz)
    expected_days = (to_date - from_date).days

    assert output == expected_days
    assert output_2nd == expected_days


def test_count_symptom_free_days_ignores_entries_outside_period(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entry_list = [
        _entry_at(
            EntryType.symptom,
            from_date - timedelta(days=1),
            tz,
            {"category": "cough", "count": 1},
        ),
        _entry_at(
            EntryType.symptom,
            to_date + timedelta(days=1),
            tz,
            {"category": "cough", "count": 1},
        ),
    ]
    expected_days = (to_date - from_date).days + 1

    output = count_symptom_free_days(entry_list, from_date, to_date, tz)

    assert output == expected_days


def test_count_symptom_free_days_ignores_payload_count(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries_1 = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "cough", "count": 1})
    ]
    entries_2 = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "cough", "count": 2})
    ]
    output_1 = count_symptom_free_days(entries_1, from_date, to_date, tz)
    output_2 = count_symptom_free_days(entries_2, from_date, to_date, tz)

    assert output_1 == output_2


def test_count_symptom_free_days_requires_tz_in_entries(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entry_list = [
        make_entry(EntryType.symptom, date_to_datetime(from_date, zone_info=None))
    ]
    with pytest.raises(ValueError) as exc_info:
        count_symptom_free_days(entry_list, from_date, to_date, tz)

    assert "Timezone not specified in symptom datetime" in str(exc_info.value)


def test_count_symptom_free_days_tz_shift_aware(dates_essentials):
    _, _, tz = dates_essentials
    entry_list = [
        make_entry(
            EntryType.symptom,
            datetime(2026, 6, 14, 21, 30, tzinfo=UTC),
            {"category": "cough", "count": 1},
        )
    ]

    from_date = date(2026, 6, 15)
    to_date = date(2026, 6, 15)
    output = count_symptom_free_days(entry_list, from_date, to_date, tz)

    assert output == 0


def test_count_symptom_free_days_incorrect_dates_handling(
    inverse_period_dates_essentials,
):
    from_date, to_date, tz = inverse_period_dates_essentials

    with pytest.raises(ValueError):
        count_symptom_free_days([], from_date, to_date, tz)


def test_count_symptom_free_days_ignores_nonsymptom_entries(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [make_entry(EntryType.walk, date_to_datetime(from_date, zone_info=tz))]
    expected_result = (to_date - from_date).days + 1

    assert count_symptom_free_days(entries, from_date, to_date, tz) == expected_result


def test_symptom_count_handles_empty_list(empty_entry_list_fixture):
    from_date, to_date, tz, entries = empty_entry_list_fixture

    output = symptom_count(entries, from_date, to_date, tz)
    assert (
        output == {}
    ), f"Nonzero frequencies for empty entry list. Symptom frequencies: {output}"


def test_symptom_count_excludes_entries_outside_dates(entrylist_and_datetimes):
    fixture_from_date, _, tz, entries = entrylist_and_datetimes
    from_date = fixture_from_date + timedelta(days=2)
    to_date = fixture_from_date + timedelta(days=4)
    output_inside = {"limping": 3, "skin": 1, "reflux": 1}

    output = symptom_count(entries, from_date, to_date, tz)

    assert output == output_inside


def test_symptom_count_ignores_zero_count(entrylist_and_datetimes):
    from_date, to_date, tz, entries = entrylist_and_datetimes

    entries = [
        make_entry(
            EntryType.symptom,
            date_to_datetime(from_date + timedelta(days=1), zone_info=tz),
            payload={
                "category": "skin",
                "severity": 1,
                "count": 0,
                "body_area": None,
                "description": "туда, семпай",
            },
        )
    ]

    expected_result = {}
    output = symptom_count(entries, from_date, to_date, tz)

    assert output == expected_result


def test_symptom_count_only_symptoms_count(dates_essentials):
    from_date, to_date, tz = dates_essentials
    the_only_symptom = "skin"
    entries = _all_entry_type_examples(from_date, tz)
    entries[0].payload["category"] = the_only_symptom

    output = symptom_count(entries, from_date, to_date, tz)

    assert output == {the_only_symptom: 1}


def test_symptom_count_use_counts(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(
            EntryType.symptom,
            from_date,
            tz,
            {"category": "vomitting", "count": 2},
            hour=1,
        )
    ]
    expected_result = {"vomitting": 2}

    assert expected_result == symptom_count(entries, from_date, to_date, tz)


def test_symptom_count_aggregates_entries(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(
            EntryType.symptom,
            from_date,
            tz,
            {"category": "vomitting", "count": 1},
            hour=1,
        ),
        _entry_at(
            EntryType.symptom,
            from_date,
            tz,
            {"category": "vomitting", "count": 1},
            hour=2,
        ),
    ]
    expected_result = {"vomitting": 2}

    assert expected_result == symptom_count(entries, from_date, to_date, tz)


def test_symptom_count_uses_default_count_1(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "vomitting"}, hour=1)
    ]
    expected_result = {"vomitting": 1}

    assert expected_result == symptom_count(entries, from_date, to_date, tz)


def test_symptom_count_handles_missing_category(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [_entry_at(EntryType.symptom, from_date, tz, {"count": 1}, hour=1)]
    output = symptom_count(entries, from_date, to_date, tz)

    assert output == {"other": 1}


def test_symptom_count_is_shift_aware(dates_essentials):
    _, _, tz = dates_essentials
    from_date = date(2026, 6, 15)
    to_date = date(2026, 6, 15)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(2026, 6, 14, 21, 30, tzinfo=UTC),
            payload={"category": "vomitting", "count": 1},
        )
    ]
    expected_result = {"vomitting": 1}

    output = symptom_count(entries, from_date, to_date, tz)

    assert output == expected_result


def test_symptom_count_handles_incorrect_daterange(dates_essentials):
    from_date, to_date, tz = dates_essentials

    with pytest.raises(ValueError):
        symptom_count([], to_date, from_date, tz)


def test_symptom_count_handles_naive_datetimes(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(from_date.year, from_date.month, from_date.day),
            payload={"category": "vomitting", "count": 5},
        )
    ]

    with pytest.raises(ValueError):
        symptom_count(entries, from_date, to_date, tz)


def test_symptom_frequency_example(dates_essentials):
    from_date, _, tz = dates_essentials
    to_date = from_date + timedelta(days=13)
    entries = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "reflux", "count": 4}),
        _entry_at(
            EntryType.symptom,
            from_date,
            tz,
            {"category": "vomitting", "count": 1},
            hour=1,
        ),
    ]
    expected_result = {"reflux": 2.0, "vomitting": 0.5}

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == expected_result


def test_symptom_frequency_handles_empty_list(empty_entry_list_fixture):
    from_date, to_date, tz, entries = empty_entry_list_fixture

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == {}


def test_symptom_frequency_excludes_entries_outside_dates(entrylist_and_datetimes):
    fixture_from_date, _, tz, entries = entrylist_and_datetimes
    from_date = fixture_from_date + timedelta(days=2)
    to_date = fixture_from_date + timedelta(days=4)
    period_days = (to_date - from_date).days + 1
    expected_result = {
        "limping": 3 / period_days * 7,
        "skin": 1 / period_days * 7,
        "reflux": 1 / period_days * 7,
    }

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == expected_result


def test_symptom_frequency_ignores_zero_count(entrylist_and_datetimes):
    from_date, to_date, tz, entries = entrylist_and_datetimes
    entries = [
        _entry_at(
            EntryType.symptom,
            from_date,
            tz,
            {
                "category": "skin",
                "severity": 1,
                "count": 0,
                "body_area": None,
                "description": "туда, семпай",
            },
            hour=14,
        )
    ]

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == {}


def test_symptom_frequency_only_symptoms_count(dates_essentials):
    from_date, to_date, tz = dates_essentials
    num_days = (to_date - from_date).days + 1
    entries = _all_entry_type_examples(from_date, tz)
    expected_result = {"skin": 1 / num_days * 7}

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == expected_result


def test_symptom_frequency_does_not_round(entrylist_and_datetimes):
    fixture_from_date, _, tz, entries = entrylist_and_datetimes
    from_date = fixture_from_date + timedelta(days=2)
    to_date = fixture_from_date + timedelta(days=4)
    num_days = (to_date - from_date).days + 1
    expected_result = {
        "limping": 3.0 / num_days * 7,
        "skin": 1.0 / num_days * 7,
        "reflux": 1.0 / num_days * 7,
    }

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert expected_result == output


def test_symptom_frequency_uses_default_count_1(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "vomitting"}, hour=1)
    ]
    expected_result = {"vomitting": 1.0}

    assert expected_result == symptom_frequency(entries, from_date, to_date, tz)


def test_symptom_frequency_handles_missing_category(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [_entry_at(EntryType.symptom, from_date, tz, {"count": 1}, hour=1)]
    output = symptom_frequency(entries, from_date, to_date, tz)

    assert output == {"other": 1.0}


def test_symptom_frequency_ignores_entries_outside_range_with_example(
    entrylist_and_datetimes,
):
    from_date, _, tz, entries = entrylist_and_datetimes

    output = symptom_frequency(entries, from_date, from_date, tz)
    expected_output = {"vomitting": 14}  # 2 / 1 * 7 == 14

    assert output == expected_output


def test_symptom_frequency_ignores_zero_counts(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "hurt", "count": 0})
    ]

    assert symptom_frequency(entries, from_date, to_date, tz) == {}


def test_symptom_frequency_handles_naive_datetimes(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(from_date.year, from_date.month, from_date.day, 1),
            payload={"category": "cough", "count": 1},
        )
    ]

    with pytest.raises(ValueError):
        symptom_frequency(entries, from_date, to_date, tz)


def test_symptom_frequency_handles_invalid_date_range(dates_essentials):
    from_date, to_date, tz = dates_essentials

    with pytest.raises(ValueError):
        symptom_frequency([], to_date, from_date, tz)


def test_symptom_frequency_tz_shift_aware(dates_essentials):
    _, _, tz = dates_essentials
    from_date = date(2026, 6, 15)
    to_date = date(2026, 6, 21)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(2026, 6, 14, 21, 30, tzinfo=UTC),
            payload={"category": "cough", "count": 1},
        )
    ]
    expected_result = {"cough": 1.0}

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert expected_result == output


def test_symptom_frequency_uses_count(dates_essentials):
    from_date, to_date, tz = dates_essentials
    entries = [
        _entry_at(EntryType.symptom, from_date, tz, {"category": "cough", "count": 5})
    ]
    expected_result = {"cough": 5.0}

    assert symptom_frequency(entries, from_date, to_date, tz) == expected_result


def test_count_state_statistics_handles_empty_entry_lists(
    empty_entry_list_fixture, empty_count_statistics_result
):
    from_date, to_date, tz, entries = empty_entry_list_fixture

    assert (
        count_state_statistics(entries, from_date, to_date, tz)
        == empty_count_statistics_result
    )


def test_count_state_statistics_ignores_unused_entrytypes(
    empty_entry_list_fixture, empty_count_statistics_result
):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    entries = [
        _entry_at(EntryType.medication, from_date, tz, {"name": "enterosgel"}),
        _entry_at(EntryType.weight, from_date, tz, {"weight_kg": 40}, hour=1),
        _entry_at(EntryType.vet_visit, from_date, tz, {"reason": "check"}, hour=2),
        _entry_at(EntryType.note, from_date, tz, {"title": "note"}, hour=3),
    ]

    output = count_state_statistics(entries, from_date, to_date, tz)

    assert output == empty_count_statistics_result


def test_count_state_statitstics_ignores_entries_outside_period(
    empty_entry_list_fixture, empty_count_statistics_result
):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    entries = [
        _entry_at(
            EntryType.walk,
            from_date - timedelta(days=1),
            tz,
            {"energy": 5, "quality": 5},
        ),
        _entry_at(
            EntryType.wellbeing,
            to_date + timedelta(days=1),
            tz,
            {"appetite": 5, "energy": 5, "mood": 5, "sleep": 5, "pain": 1},
        ),
    ]

    output = count_state_statistics(entries, from_date, to_date, tz)

    assert output == empty_count_statistics_result


def test_count_state_statistics_handles_multiple_entries_in_one_day(
    empty_entry_list_fixture, empty_count_statistics_result
):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            {
                "duration_minutes": 30,
                "distance_km": 1,
                "energy": 4,
                "quality": 2,
            },
            hour=1,
        ),
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            {
                "duration_minutes": 30,
                "distance_km": 1,
                "energy": 5,
                "quality": 5,
            },
            hour=3,
        ),
    ]

    expected_result = empty_count_statistics_result
    expected_result["energy"] = {
        "mean": 4.5,
        "std": 0.5,
        "min": 4,
        "max": 5,
    }
    expected_result["quality"] = {
        "mean": 3.5,
        "std": 1.5,
        "min": 2,
        "max": 5,
    }

    output = count_state_statistics(entries, from_date, to_date, tz)

    assert expected_result == output


def test_count_state_statistics_does_not_round(empty_entry_list_fixture):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            {
                "duration_minutes": 30,
                "distance_km": 1,
                "energy": 4,
                "quality": 2,
            },
            hour=1,
        ),
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            {
                "duration_minutes": 30,
                "distance_km": 1,
                "energy": 5,
                "quality": 5,
            },
            hour=3,
        ),
    ]

    output = count_state_statistics(entries, from_date, to_date, tz)

    assert output["energy"]["mean"] == 4.5
    assert output["quality"]["mean"] == 3.5
    assert output["quality"]["std"] == 1.5


def test_count_state_statistics_tz_shift_aware(empty_entry_list_fixture):
    _, _, tz, _ = empty_entry_list_fixture
    from_date = date(2026, 6, 15)
    to_date = date(2026, 6, 15)
    entries = [
        make_entry(
            EntryType.walk,
            datetime(2026, 6, 14, 21, 30, tzinfo=UTC),
            {"energy": 5, "quality": 4},
        )
    ]

    output = count_state_statistics(entries, from_date, to_date, tz)

    assert output["energy"]["mean"] == 5
    assert output["quality"]["mean"] == 4


def test_count_state_statistics_handles_naive_datetimes(empty_entry_list_fixture):
    from_date, to_date, tz, entries = empty_entry_list_fixture
    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            payload={"duration_minutes": 30, "distance_km": 1, "energy": 5},
            hour=1,
        )
    ]
    with pytest.raises(ValueError):
        count_state_statistics(entries, from_date, to_date, tz)


def test_count_state_statistics_handles_invalid_date_range(
    inverse_period_dates_essentials,
):
    from_date, to_date, tz = inverse_period_dates_essentials

    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            payload={"duration_minutes": 30, "distance_km": 1, "energy": 5},
            hour=1,
        )
    ]
    with pytest.raises(ValueError):
        count_state_statistics(entries, from_date, to_date, tz)


def test_count_state_statistics_handles_bool_values(dates_essentials):
    from_date, to_date, tz = dates_essentials

    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            payload={"duration_minutes": 30, "distance_km": True, "energy": 5},
            hour=1,
        )
    ]

    with pytest.raises(TypeError):
        count_state_statistics(entries, from_date, to_date, tz)


def test_count_state_statistics_is_deterministic(dates_essentials):
    from_date, to_date, tz = dates_essentials

    entries = [
        _entry_at(
            EntryType.walk,
            from_date,
            tz,
            payload={"duration_minutes": 30, "distance_km": 1, "energy": 5},
            hour=1,
        )
    ]
    output_1 = count_state_statistics(entries, from_date, to_date, tz)
    output_2 = count_state_statistics(entries, from_date, to_date, tz)

    assert output_1 == output_2
