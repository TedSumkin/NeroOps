"""This file contains tests for health-analytics related classes and methods"""

from datetime import UTC, date, datetime, timezone, timedelta

import pytest
from neroops.models import Entry, EntryType

from neroops.services.health_analytics import count_symptoms_free_days
from copy import deepcopy


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


@pytest.fixture()
def dates_essentials():
    return (2026, 1, timezone(timedelta(hours=3)))


def test_count_symptoms_free_days_handles_empty_entry_lists(dates_essentials):
    year, month, tz = dates_essentials
    """test if count_symptoms_free_days correctly handles empty entry lists"""
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=3)
    empty_entry_list = []

    output = count_symptoms_free_days(empty_entry_list, from_date, to_date, tz)
    period_days = (to_date - from_date).days + 1
    assert (
        output == period_days
    ), f"Inaccuate handling of empty entry list, number of days returned = {output}, number of days expected = {period_days}"


def test_handles_multiple_entries_in_one_day(dates_essentials):
    """test if count_symptoms_free_days correctly handles multiple entries in one day"""
    year, month, tz = dates_essentials
    entry_list = [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=5, hour=13, tzinfo=tz),
        ),
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=5, hour=13, minute=1, tzinfo=tz),
        ),
    ]

    entry_list_2nd = deepcopy(entry_list) + [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=5, hour=20, tzinfo=tz),
        )
    ]
    from_date = date(year=2026, month=1, day=1)
    to_date = date(year=2026, month=1, day=7)
    output = count_symptoms_free_days(entry_list, from_date, to_date, tz)
    output_2nd = count_symptoms_free_days(entry_list_2nd, from_date, to_date, tz)
    expected_days = (to_date - from_date).days

    assert (
        output == expected_days
    ), "Incorrect handling of two symptom entries in one day in count_symptoms_free_days"
    assert (
        output_2nd == expected_days
    ), "Incorrect handling of three symptom entries in one day count_symptoms_free_days"


def test_ignores_entries_outside_period(dates_essentials):
    """Test if entries outside scecified period are ignored"""
    year, month, tz = dates_essentials
    import calendar

    entry_list = [
        make_entry(
            EntryType.symptom, datetime(year=year, month=month, day=day, tzinfo=tz)
        )
        for day in range(1, calendar.monthrange(year, month)[-1] + 1)
    ]
    from_date = date(year=year, month=month, day=2)
    to_date = date(year=year, month=month, day=7)
    expected_days = (to_date - from_date).days + 1

    output = count_symptoms_free_days(entry_list, from_date, to_date, tz)

    assert (
        output == expected_days,
    ), "Symptom-free day counter function counts days beyond specified boundaries"


def test_requires_tz_in_entries(dates_essentials):
    year, month, tz = dates_essentials
    entry_list = [
        make_entry(EntryType.symptom, datetime(year=year, month=month, day=1))
    ]
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=2)
    with pytest.raises(ValueError) as exc_info:
        count_symptoms_free_days(entry_list, from_date, to_date, tz)

    assert "Timezone not specified in symptom datetime" in str(exc_info.value)


def test_tz_shift_aware(dates_essentials):
    """Tests correct handling of timezone-related shift in count_symptoms_free_days"""
    year, month, tz = dates_essentials

    day = 18
    hour = 23
    utc_tz = timezone(timedelta(hours=0))
    entry_list = [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=day, hour=hour, tzinfo=utc_tz),
        )
    ]
    from_date = date(year=year, month=month, day=day - 1)
    to_date = date(year=year, month=month, day=day)
    expected_result = (to_date - from_date).days + 1

    tz = timezone(timedelta(hours=3))
    output = count_symptoms_free_days(entry_list, from_date, to_date, tz)
    assert output == expected_result, "Timezone is incorrectly handled"


def test_incorrect_dates_handling(dates_essentials):

    import calendar

    year, month, tz = dates_essentials

    from_date = datetime(year=year, month=month, day=2)
    to_date = datetime(year=year, month=month, day=1)
    entry_list = [
        make_entry(EntryType.symptom, datetime(year=year, month=month, day=day))
        for day in range(1, calendar.monthrange(year, month)[-1] + 1)
    ]

    with pytest.raises(ValueError) as exc_info:
        result = count_symptoms_free_days(entry_list, from_date, to_date, tz)
