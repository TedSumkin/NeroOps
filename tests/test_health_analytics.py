"""This file contains tests for health-analytics related classes and methods"""

from datetime import UTC, date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pytest
from neroops.models import Entry, EntryType

from neroops.services.health_analytics import (
    count_symptoms_free_days,
    symptom_frequency,
)
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
    zone_info = ZoneInfo("Europe/Moscow")
    return (2026, 1, zone_info)


def test_handles_empty_entry_lists(dates_essentials):
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


def test_ignores_payload_count(dates_essentials):
    """count_symptom_free_days must ignore payload["count"] values"""
    pass


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


def test_symptom_frequency_handles_empty_list(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=7)
    entry_list = []

    output = symptom_frequency(entry_list, from_date, to_date, "Europe/Moscow")
    assert (
        output == {}
    ), f"Nonzero frequencies for empty entry list. Symptom frequencies: {output}"


@pytest.fixture()
def entrylist_and_datetimes():
    year = 2026
    month = 1
    zone_info = ZoneInfo("Europe/Moscow")
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(
                year=year,
                month=month,
                day=1,
                hour=12,
            ),
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
            datetime(year=year, month=month, day=2, hour=12, tzinfo=zone_info),
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
            datetime(year=year, month=month, day=3, hour=12, tzinfo=zone_info),
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
            datetime(year=year, month=month, day=4, hour=14, tzinfo=zone_info),
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
            datetime(year=year, month=month, day=5, hour=14, tzinfo=zone_info),
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
            datetime(year=year, month=month, day=6, hour=14, tzinfo=zone_info),
            payload={
                "category": "ears",
                "severity": 1,
                "count": 1,
                "body_area": None,
                "description": "не туда, семпай",
            },
        ),
    ]
    return (year, month, zone_info, entries)


def test_symptom_frequency_excludes_entries_outside_dates(entrylist_and_datetimes):

    year, month, tz, entries = entrylist_and_datetimes
    from_date = date(year=year, month=month, day=3)
    to_date = date(year=year, month=month, day=5)
    num_days = (to_date - from_date).days + 1

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert (
        "vomitting" not in output and "gas" not in output and "ears" not in output,
        "Symptom_frequency incorrectly handles entries outside specified date range",
    )


def test_symptom_frequency_ignores_zero_count(entrylist_and_datetimes):

    year, month, tz, entries = entrylist_and_datetimes

    from_date = date(year=2026, month=1, day=1)
    to_date = date(year=2026, month=1, day=7)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=3, hour=14, tzinfo=tz),
            payload={
                "category": "skin",
                "severity": 1,
                "count": 0,
                "body_area": None,
                "description": "туда, семпай",
            },
        )
    ]

    # expected_result = {"limping": 3.0 / num_days * 7, "skin": 1.0 / num_days * 7, "reflux": 1. / num_days * 7}
    expected_result = {}
    output = symptom_frequency(entries, from_date, to_date, tz)
    assert (
        output == expected_result
    ), "symptom_frequency incorrectly handles symptoms with zero counts"


def test_symptom_frequency_only_symptoms_count(dates_essentials):
    # setup dates and datetimes
    year, month, tz = dates_essentials
    from_day = 5
    to_day = 10
    from_date = date(year=year, month=month, day=from_day)
    to_date = date(year=year, month=month, day=to_day)
    num_days = (to_date - from_date).days + 1
    # make all possible entries in a period from from_date to to_date

    datetimes = [
        datetime(
            year=year,
            month=month,
            day=from_day + i % (to_day - from_day + 1),
            hour=12,
            tzinfo=tz,
        )
        for i in range(9)
    ]

    # make entries of all possible entry types
    entries = [
        make_entry(
            EntryType.symptom,
            datetimes[0],
            payload={
                "category": "skin",
                "severity": 1,
                "count": 1,
                "body_area": None,
                "description": "покраснение кожи",
            },
        ),
        make_entry(
            EntryType.feeding,
            datetimes[1],
            payload={
                "food": "royal canin",
                "amount": "200",
                "unit": "g",
                "appetite": 5,
                "reaction": "tasty",
            },
        ),
        make_entry(
            EntryType.walk,
            datetimes[2],
            payload={
                "duration_minutes": 20,
                "distance_km": 0.6,
                "energy": 5,
                "quality": 5,
            },
        ),
        make_entry(
            EntryType.wellbeing,
            datetimes[3],
            payload={
                "appetite": 5,
                "energy": 5,
                "mood": 5,
                "sleep": 5,
                "pain": 1,
            },
        ),
        make_entry(
            EntryType.training,
            datetimes[4],
            payload={
                "duration_minutes": 15,
                "commands": ["sit", "lay", "stay"],
                "engagement": 3,
                "result": "Потренировались в целом хорошо, подошли понюхаться к другим собакам в том числе",
            },
        ),
        make_entry(
            EntryType.medication,
            datetimes[5],
            payload={"name": "бриллиантовые глазки", "dose": 5, "unit": "mg"},
        ),
        make_entry(EntryType.weight, datetimes[6], payload={"weight_kg": 40}),
        make_entry(
            EntryType.vet_visit,
            datetimes[7],
            payload={
                "reason": "vomitting",
                "diagnosis": "reflux",
                "recommendations": "таблет_очки",
                "follow_up_date": date(year=year, month=month, day=26),
            },
        ),
        make_entry(EntryType.note, datetimes[8], payload={"title": "ахахахаха"}),
    ]

    # calculate expected result
    expected_results = entries[0].payload["count"] / num_days * 7

    output = symptom_frequency(entries, from_date, to_date, tz)
    # check if symptom is even taken into account
    assert entries[0].payload["category"] in output, "Symptom is ignored"
    # check if only symptom is accounted
    assert (
        len(output.keys()) == 1
    ), "Multiple entries in symptom_frequency output dict with the only symptom"
    # check symptom frequency
    assert output[entries[0].payload["category"]] == expected_results, "Incorrect"


def test_symptom_does_not_round(entrylist_and_datetimes):

    # setup dates and datetimes
    year, month, tz, entries = entrylist_and_datetimes
    from_date = date(year=year, month=month, day=3)
    to_date = date(year=year, month=month, day=5)
    num_days = (to_date - from_date).days + 1

    # calculate expected results
    expected_result = {
        "limping": 3.0 / num_days * 7,
        "skin": 1.0 / num_days * 7,
        "reflux": 1.0 / num_days * 7,
    }

    output = symptom_frequency(entries, from_date, to_date, tz)

    # check if output is equal to the expected one
    assert (
        expected_result == output,
        "Symptom_frequency probably rounds values",
    )
