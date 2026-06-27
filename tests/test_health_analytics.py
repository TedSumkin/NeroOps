"""This file contains tests for health-analytics related classes and methods"""

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from neroops.models import Entry, EntryType
from neroops.services.health_analytics import (
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


@pytest.fixture()
def dates_essentials() -> tuple[int, int, ZoneInfo]:
    year = 2026
    month = 1
    zone_info = ZoneInfo("Europe/Moscow")
    return (year, month, zone_info)


@pytest.fixture()
def entrylist_and_datetimes() -> tuple[int, int, ZoneInfo, list[EntryType]]:
    year = 2026
    month = 1
    zone_info = ZoneInfo("Europe/Moscow")
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year=year, month=month, day=1, hour=12, tzinfo=zone_info),
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


def test_count_symptom_free_days_deterministic(entrylist_and_datetimes):
    year, month, tz, entries = entrylist_and_datetimes
    from_date = date(year, month, 1)
    to_date = date(year, month, 28)

    output_1 = count_symptom_free_days(entries, from_date, to_date, tz)
    output_2 = count_symptom_free_days(entries, from_date, to_date, tz)

    assert (
        output_1 == output_2
    ), "count_symptom_free_days is nondeterministic, different runs yield different results"


def test_count_symptom_free_days_handles_empty_entry_lists(dates_essentials):
    year, month, tz = dates_essentials
    """test if count_symptom_free_days correctly handles empty entry lists"""
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=3)
    empty_entry_list = []

    output = count_symptom_free_days(empty_entry_list, from_date, to_date, tz)
    period_days = (to_date - from_date).days + 1
    assert output == period_days, (
        "Inaccuate handling of empty entry list,"
        " number of days returned = {output}, number of days expected = {period_days}"
    )


def test_count_symptom_free_days_handles_multiple_entries_in_one_day(dates_essentials):
    """test if count_symptom_free_days correctly handles multiple entries in one day"""
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
    output = count_symptom_free_days(entry_list, from_date, to_date, tz)
    output_2nd = count_symptom_free_days(entry_list_2nd, from_date, to_date, tz)
    expected_days = (to_date - from_date).days

    assert (
        output == expected_days
    ), "Incorrect handling of two symptom entries in one day in count_symptom_free_days"
    assert (
        output_2nd == expected_days
    ), "Incorrect handling of three symptom entries in one day count_symptom_free_days"


def test_count_symptom_free_days_ignores_entries_outside_period(dates_essentials):
    """Test if entries outside scecified period are ignored"""
    year, month, tz = dates_essentials
    import calendar

    from_date = date(year=year, month=month, day=2)
    to_date = date(year=year, month=month, day=7)
    entry_list = [
        make_entry(
            EntryType.symptom, datetime(year=year, month=month, day=day, tzinfo=tz)
        )
        for day in range(1, calendar.monthrange(year, month)[-1] + 1)
        if (day < from_date.day) or (day > to_date.day)
    ]
    expected_days = (to_date - from_date).days + 1

    output = count_symptom_free_days(entry_list, from_date, to_date, tz)

    assert (
        output == expected_days
    ), "Symptom-free day counter function counts days beyond specified boundaries"


def test_count_symptom_free_days_ignores_payload_count(dates_essentials):
    """count_symptom_free_days must ignore payload["count"] values"""
    # setup dates
    year, month, tz = dates_essentials
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=2)

    entries_1 = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, tzinfo=tz),
            payload={"category": "cough", "count": 1},
        )
    ]

    entries_2 = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, tzinfo=tz),
            payload={"category": "cough", "count": 2},
        )
    ]
    output_1 = count_symptom_free_days(entries_1, from_date, to_date, tz)
    output_2 = count_symptom_free_days(entries_2, from_date, to_date, tz)
    assert (
        output_1 == output_2
    ), 'count_symptom_free_days does not ignore payload["count"]'


def test_count_symptom_free_days_requires_tz_in_entries(dates_essentials):
    year, month, tz = dates_essentials
    entry_list = [
        make_entry(EntryType.symptom, datetime(year=year, month=month, day=1))
    ]
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=2)
    with pytest.raises(ValueError) as exc_info:
        count_symptom_free_days(entry_list, from_date, to_date, tz)

    assert "Timezone not specified in symptom datetime" in str(exc_info.value)


def test_count_symptom_free_days_tz_shift_aware(dates_essentials):
    """Tests correct handling of timezone-related shift in count_symptom_free_days"""
    year, month, tz = dates_essentials

    day = 14
    hour = 23
    minute = 30
    utc_tz = timezone(timedelta(hours=0))
    entry_list = [
        make_entry(
            EntryType.symptom,
            datetime(
                year=year, month=month, day=day, hour=hour, minute=minute, tzinfo=utc_tz
            ),
        )
    ]
    from_date = date(year=year, month=month, day=day + 1)
    to_date = date(year=year, month=month, day=day + 2)
    expected_result = 1

    tz = timezone(timedelta(hours=3))
    output = count_symptom_free_days(entry_list, from_date, to_date, tz)
    assert output == expected_result, "Timezone is incorrectly handled"


def test_count_symptom_free_days_incorrect_dates_handling(dates_essentials):
    """Test if count_symptom_free_days raises ValueError when to_date is earlier than from_date"""
    year, month, tz = dates_essentials

    from_date = datetime(year=year, month=month, day=2)
    to_date = datetime(year=year, month=month, day=1)
    entry_list = []

    with pytest.raises(ValueError):
        count_symptom_free_days(entry_list, from_date, to_date, tz)


def test_count_symptom_free_days_ignores_nonsymptom_entries(dates_essentials):
    """hui"""
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.walk, datetime(year, month, from_date.day, hour=1, tzinfo=tz)
        )
    ]
    expected_result = (to_date - from_date).days + 1
    assert (
        count_symptom_free_days(entries, from_date, to_date, tz) == expected_result
    ), "count_symptom_free_days does not ignore non-symptom entries"


def test_symptom_count_handles_empty_list(dates_essentials):
    year, month, _ = dates_essentials  # pyright:ignore
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=7)
    entry_list = []

    output = symptom_count(entry_list, from_date, to_date, "Europe/Moscow")
    assert (
        output == {}
    ), f"Nonzero frequencies for empty entry list. Symptom frequencies: {output}"


def test_symptom_count_excludes_entries_outside_dates(entrylist_and_datetimes):

    year, month, tz, entries = entrylist_and_datetimes
    from_date = date(year=year, month=month, day=3)
    to_date = date(year=year, month=month, day=5)
    output = symptom_count(entries, from_date, to_date, tz)
    output_inside = {"limping": 3, "skin": 1, "reflux": 1}
    assert output == output_inside, (
        "symptom_count incorrectly handles entries outside specified date range",
    )


def test_symptom_count_ignores_zero_count(entrylist_and_datetimes):

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
    output = symptom_count(entries, from_date, to_date, tz)
    assert (
        output == expected_result
    ), "symptom_frequency incorrectly handles symptoms with zero counts"


def test_symptom_count_only_symptoms_count(dates_essentials):
    # setup dates and datetimes
    year, month, tz = dates_essentials
    from_day = 5
    to_day = 10
    from_date = date(year=year, month=month, day=from_day)
    to_date = date(year=year, month=month, day=to_day)
    the_only_symptom = "skin"
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
                "category": the_only_symptom,
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
                "reason": the_only_symptom,
                "diagnosis": "reflux",
                "recommendations": "таблет_очки",
                "follow_up_date": date(year=year, month=month, day=26),
            },
        ),
        make_entry(EntryType.note, datetimes[8], payload={"title": "ахахахаха"}),
    ]
    symptom_only_entries = [entries[0]]

    # calculate expected result
    expected_results = symptom_count(symptom_only_entries, from_date, to_date, tz)

    output = symptom_count(entries, from_date, to_date, tz)
    # check if symptom is even taken into account
    assert the_only_symptom in output, "Symptom is ignored"
    # check if only symptom is accounted
    assert (
        len(output.keys()) == 1
    ), "Multiple entries in symptom_count output dict with the only symptom"
    # check symptom count
    assert output == expected_results, "symptom_count counts non-symptom entries"


def test_symptom_count_use_counts(dates_essentials):
    """test if symptom_count sums counts instead of counting correpsonging entries"""
    year, month, tz = dates_essentials

    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting", "count": 2},
        )
    ]
    expected_result = {"vomitting": 2}
    assert expected_result == symptom_count(entries, from_date, to_date, tz)
    return


def test_symptom_count_aggregates_entries(dates_essentials):
    """test if symptom_count sums counts instead of counting correpsonging entries"""
    year, month, tz = dates_essentials

    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting", "count": 1},
        ),
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting", "count": 1},
        ),
    ]
    expected_result = {"vomitting": 2}
    assert expected_result == symptom_count(entries, from_date, to_date, tz)
    return


def test_symptom_count_uses_default_count_1(dates_essentials):
    """test if symptom_count falls back to count 1 by default if 'count' is not specified"""
    year, month, tz = dates_essentials

    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting"},
        ),
    ]
    expected_result = {"vomitting": 1}
    assert expected_result == symptom_count(entries, from_date, to_date, tz)
    return


def test_symptom_count_handles_missing_category(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"count": 1},
        )
    ]
    output = symptom_count(entries, from_date, to_date, tz)
    assert output == {
        "other": 1
    }, "symptom_count: missing category does not fall back to 'other'"
    return


def test_symptom_count_is_shift_aware(dates_essentials):
    year, month, tz = dates_essentials

    utc_tz = ZoneInfo("UTC")

    from_date = date(year, month, 2)
    to_date = date(year, month, 3)
    hour = 21
    minute = 30

    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day - 1, hour, minute, tzinfo=utc_tz),
            payload={"category": "vomitting", "count": 1},
        )
    ]
    expected_result = {"vomitting": 1}
    output = symptom_count(entries, from_date, to_date, tz)
    assert (
        output == expected_result
    ), "symptom_count incorrectly handles timezone-related shifts"


def test_symptom_count_handles_incorrect_daterange(dates_essentials):
    """test if symptom_count raises ValueError if to_date is earlier than from_date"""
    year, month, tz = dates_essentials
    from_date = date(year, month, 5)
    to_date = date(year, month, 1)

    with pytest.raises(ValueError):
        symptom_count([], from_date, to_date, tz)
    return


def test_symptom_count_handles_naive_datetimes(dates_essentials):
    """test if symptom_count raises ValueError if tz is not specified in occurred_at fields"""
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 2)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day),
            payload={"category": "vomitting", "count": 5},
        )
    ]

    with pytest.raises(ValueError):
        symptom_count(entries, from_date, to_date, tz)
    return


def test_symptom_frequency_example(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 14)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, tzinfo=tz),
            payload={"category": "reflux", "count": 4},
        ),
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, tzinfo=tz),
            payload={"category": "vomitting", "count": 1},
        ),
    ]
    expected_result = {"reflux": 2.0, "vomitting": 0.5}
    output = symptom_frequency(entries, from_date, to_date, tz)
    assert (
        output == expected_result
    ), "symptom_frequency calculates frequencies incorrectly"


def test_symptom_frequency_handles_empty_list(dates_essentials):
    year, month, tz = dates_essentials  # pyright:ignore
    from_date = date(year=year, month=month, day=1)
    to_date = date(year=year, month=month, day=7)
    entry_list = []

    output = symptom_frequency(entry_list, from_date, to_date, "Europe/Moscow")
    assert (
        output == {}
    ), f"Nonzero frequencies for empty entry list. Symptom frequencies: {output}"


def test_symptom_frequency_excludes_entries_outside_dates(entrylist_and_datetimes):

    year, month, tz, entries = entrylist_and_datetimes
    from_date = date(year=year, month=month, day=3)
    to_date = date(year=year, month=month, day=5)
    period_days = (to_date - from_date).days + 1

    output = symptom_frequency(entries, from_date, to_date, tz)

    assert "vomitting" not in output and "gas" not in output and "ears" not in output, (
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


def test_symptom_frequency_does_not_round(entrylist_and_datetimes):

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
    assert expected_result == output, "Symptom_frequency probably rounds values"


def test_symptom_frequency_uses_default_count_1(dates_essentials):
    """test if symptom_frequency falls back to count 1 by default if 'count' is not specified"""
    year, month, tz = dates_essentials

    from_date = date(year, month, 1)
    to_date = date(year, month, 7)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting"},
        ),
    ]
    expected_result = {"vomitting": 1}
    assert expected_result == symptom_frequency(entries, from_date, to_date, tz)
    return


def test_symptom_frequency_handles_missing_category(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 7)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"count": 1},
        )
    ]
    output = symptom_frequency(entries, from_date, to_date, tz)
    assert output == {
        "other": 1
    }, "symptom_count: missing category does not fall back to 'other'"
    return


def test_symptom_frequency_ignores_entries_outside_range_with_example(
    entrylist_and_datetimes,
):
    year, month, tz, entries = entrylist_and_datetimes

    from_day = date(year, month, 1)
    to_day = date(year, month, 1)

    output = symptom_frequency(entries, from_day, to_day, tz)
    expected_output = {"vomitting": 14}  # 2 / 1 * 7 == 14

    assert output == expected_output, (
        "symptom_frequency ignores symptom entries outside specified date range,"
        " but incorrectly handles counts inside it"
    )


def test_symptom_frequency_ignores_zero_counts(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 2)

    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "hurt", "count": 0},
        )
    ]
    assert (
        symptom_frequency(entries, from_date, to_date, tz) == {}
    ), "symptom_frequency does not ignore zero-count entries"


def test_symptom_frequency_handles_naive_datetimes(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 10)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, 1, 1),
            payload={"category": "cough", "count": 1},
        )
    ]
    with pytest.raises(ValueError):
        count_symptom_free_days(entries, from_date, to_date, tz)


def test_symptom_frequency_handles_invalid_date_range(dates_essentials):
    year, month, tz = dates_essentials

    from_date = date(year, month, 5)
    to_date = date(year, month, 1)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "vomitting", "count": 1},
        )
    ]

    with pytest.raises(ValueError):
        symptom_frequency(entries, from_date, to_date, tz)


def test_symptom_frequency_tz_shift_aware(dates_essentials):
    year, month, tz = dates_essentials

    from_date = date(year, month, 2)
    to_date = date(year, month, 8)
    utc_tz = ZoneInfo("UTC")

    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day - 1, 21, 30, tzinfo=utc_tz),
            payload={"category": "cough", "count": 1},
        )
    ]
    expected_result = {"cough": 1}
    output = symptom_frequency(entries, from_date, to_date, tz)

    assert (
        expected_result == output
    ), "symptom_frequency incorrectly handles timezone shift"


def test_symptom_frequency_uses_count(dates_essentials):
    year, month, tz = dates_essentials
    from_date = date(year, month, 1)
    to_date = date(year, month, 7)
    entries = [
        make_entry(
            EntryType.symptom,
            datetime(year, month, from_date.day, 1, tzinfo=tz),
            payload={"category": "cough", "count": 5},
        )
    ]
    expected_result = {"cough": 5}
    assert (
        symptom_frequency(entries, from_date, to_date, tz) == expected_result
    ), "symptom_frequency incorrectly uses symptom payload counts or does not use them"


def test_state_statitstics_ignores_entries_outside_period(dates_essentials):
    year, month, tz = dates_essentials

    entries = [
        make_entry(
            EntryType.walk,
            datetime(year=year, month=month, day=2, tzinfo=tz),
            payload={
                "duration_minutes": 25,
                "distance_km": 1,
                "energy": 5,
                "quality": 5,
            },
        ),
        make_entry(
            EntryType.walk,
            datetime(year=year, month=month, day=3, tzinfo=tz),
            payload={
                "duration_minutes": 20,
                "distance_km": 1,
                "energy": 5,
                "quality": 5,
            },
        ),
        make_entry(
            EntryType.feeding,
            datetime(year=year, month=month, day=3, tzinfo=tz),
            payload={
                "food": "Royal Caning",
                "amount": 100,
                "unit": "g",
                "appetite": 5,
                "reaction": None,
            },
        ),
    ]
