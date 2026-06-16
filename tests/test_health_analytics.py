""" This file contains tests for health-analytics related classes and methods"""

from datetime import UTC, date, datetime

import pytest
from backend.neroops.models import Entry, EntryType

from backend.neroops.services.health_analytics import count_symptoms_free_days


def make_entry(entry_type: EntryType, occurred_at: datetime, payload: dict | None = None):
    return Entry(
          id=f"{entry_type.value}-{occurred_at.isoformat()}",
          pet_id="pet-id",
          type=entry_type,
          occurred_at=occurred_at,
          payload=payload or {},
    )
