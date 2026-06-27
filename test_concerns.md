# Test concerns for health analytics

This file summarizes missing, weak, or failing tests around
`backend/neroops/services/health_analytics.py` and
`tests/test_health_analytics.py`.

## Current check results

Command:

```bash
./.venv/bin/pytest tests/test_health_analytics.py -q
```

Current result:

```text
5 failed, 9 passed
```

Command:

```bash
./.venv/bin/ruff check tests/test_health_analytics.py backend/neroops/services/health_analytics.py
```

Current result:

```text
15 errors
```

Important Ruff findings:

- several unused imports in `health_analytics.py`;
- three tuple asserts that are always truthy;
- an unfinished state-statistics test;
- several unused local variables;
- line-length issues.

## Contract/name mismatch

`CONTRACTS.md` and `HEALTH_ANALYTICS_TEST_PLAN.md` describe:

```python
count_symptom_free_days(...)
```

The current implementation and tests use:

```python
count_symptoms_free_days(...)
```

Tests should either be moved to the contract name, or the contract/docs should be
updated intentionally.

## `count_symptom_free_days` / `count_symptoms_free_days`

Partially covered:

- empty entries;
- multiple symptoms on one day;
- naive datetime;
- some timezone behavior.

Missing or weak tests (fix them):

- [x] `test_ignores_payload_count` is empty and only contains `pass`;
- [x] the out-of-period test uses a tuple assert, so it always passes;
- [x] the out-of-period scenario should use only symptoms strictly before/after the
  period if it intends to check "no symptoms inside the period";
- [x] the timezone test should match the plan exactly:
  `2026-06-14 21:30 UTC` should be local `2026-06-15` in `Europe/Moscow`;
- [x] invalid date range should be tested with an empty list and `date` objects, so
  it checks the date-range error rather than a naive datetime error;
- [x] add a test that non-symptom entries do not make a day symptomatic.

## `symptom_count`

The function exists, but there are no tests for it yet.

Needed tests:

- [x] empty list returns `{}`;
- [x] only `EntryType.symptom` entries are counted;
- [x] entries outside the inclusive period are ignored;
- [x] `payload["count"]` is summed, not row count;
- [x] multiple rows with the same category are accumulated;
- [x] missing `count` falls back to `1`;
- [x] missing `category` follows the agreed defensive category from the contract;
- [x] zero-count categories are either excluded or intentionally documented;
- [x] timezone boundary near midnight;
- [x] invalid date range raises `ValueError`;
- [x] naive datetime raises `ValueError`.

## `symptom_frequency`

Covered partly, but several tests are currently failing or weak.

Needed tests:

- [x] explicit contract example:
  14 days, 4 `reflux` episodes and 1 `vomiting` episode should return
  `{"reflux": 2.0, "vomiting": 0.5}`;
- [x] `payload["count"]` affects frequency, instead of counting symptom rows;
- [x] missing `count` falls back to `1`;
- [x] missing `category` follows the agreed defensive category;
- [x] entries outside the period are ignored with exact expected output;
- [x] categories with zero count are not included if that remains the contract;
- [x] no rounding is performed;
- [x] invalid date range raises `ValueError`;
- [x] naive datetime raises `ValueError`;
- [x] timezone boundary near midnight.

## `count_state_statistics`

The function is currently a stub using `...`.

The started test is unfinished:

- it does not import or call `count_state_statistics`;
- it has no assertion;
- it uses `datetime(..., tz=tz)`, which raises `TypeError`;
- the `entries` local variable is unused.

Needed tests:

- [ ] empty input;
- [ ] only `EntryType.walk`, `EntryType.feeding`, `EntryType.wellbeing`, and
  `EntryType.training` are included;
- [ ]  entries outside the inclusive period are ignored;
- [ ]  multiple entries on one day are handled correctly;
- [ ]  statistics are not rounded;
- [ ]  timezone boundary near midnight;
- [ ]  naive datetime raises `ValueError`;
- [ ]  invalid date range raises `ValueError`;
- [ ]  bool values are not treated as numeric scores;
- [ ]  the function is deterministic and does not mutate inputs.

## `build_health_period_metrics`

The function exists, but there are no tests for it.

Needed tests:

- all `HealthPeriodMetrics` fields are populated;
- `period_days` uses the inclusive formula;
- `symptom_free_days` follows the symptom-free-days function;
- `symptom_free_day_share = symptom_free_days / period_days`;
- `symptom_days = period_days - symptom_free_days`;
- `symptom_counts` contains absolute episode counts;
- `total_symptom_episodes = sum(symptom_counts.values())`;
- `symptom_episodes_per_7_days = total_symptom_episodes / period_days * 7`;
- `average_scores` includes the expected score keys;
- bool and non-numeric values are ignored in averages;
- entries outside the period are ignored;
- timezone boundary near midnight;
- invalid date range raises `ValueError`;
- naive datetime raises `ValueError`;
- output validates as `HealthPeriodMetrics`.

Important current bug candidate:

```python
symptom_episodes_per_7_days=total_symptom_episodes / 7
```

The contract says:

```python
total_symptom_episodes / period_days * 7
```

## `compare_health_periods`

The contract describes this function, but implementation and tests are absent.

Needed tests:

- compares two already-built `HealthPeriodMetrics` objects;
- absolute delta is always `current - previous`;
- relative delta is `absolute / abs(previous)`;
- previous value `0` gives `relative is None`;
- period length differences do not matter because share/rate fields are used;
- `average_scores` only compares keys present in both periods;
- no automatic "improved" interpretation is added.

## `find_food_symptom_associations`

The contract describes this function, but implementation and tests are absent.

Needed tests:

- empty list returns `[]`;
- invalid `window_hours` raises `ValueError`;
- invalid `min_feedings` raises `ValueError`;
- naive datetime raises `ValueError`;
- symptom is assigned to the nearest previous feeding, not all previous
  feedings;
- symptom outside the window is ignored;
- symptom with the same timestamp as feeding is not considered subsequent;
- food names are normalized with `strip().casefold()`;
- `payload["count"]` is summed in `symptom_counts`;
- latency is counted once per symptom row, not once per `count`;
- foods below `min_feedings` are excluded;
- sorting is stable:
  `association_rate desc`, `feeding_count desc`, `food asc`.

## Cleanup before trusting results

- Fix tuple asserts in `tests/test_health_analytics.py`.
- Remove naive datetimes from shared fixtures unless the specific test is about
  naive datetime behavior.
- Keep each test focused on one reason to fail.
- Decide whether tests should target the current implementation name or the
  contract name.
- Re-run:

```bash
./.venv/bin/pytest tests/test_health_analytics.py -q
./.venv/bin/ruff check tests/test_health_analytics.py backend/neroops/services/health_analytics.py
```
