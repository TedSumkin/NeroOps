import io
from datetime import UTC, datetime
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient
from neroops.main import app


def test_entry_lifecycle_is_idempotent() -> None:
    with TestClient(app) as client:
        bootstrap = client.get("/api/v1/bootstrap")
        assert bootstrap.status_code == 200
        pet_id = bootstrap.json()["pet"]["id"]

        entry_id = str(uuid4())
        body = {
            "id": entry_id,
            "pet_id": pet_id,
            "type": "feeding",
            "occurred_at": datetime.now(UTC).isoformat(),
            "note": "После прогулки",
            "payload": {"food": "Сухой корм", "amount": 250, "unit": "g", "appetite": 5},
        }

        created = client.post("/api/v1/entries", json=body)
        repeated = client.post("/api/v1/entries", json=body)
        assert created.status_code == 200
        assert repeated.status_code == 200
        assert repeated.json()["id"] == entry_id

        page = client.get("/api/v1/entries", params={"type": "feeding"})
        assert page.status_code == 200
        assert page.json()["total"] == 1

        updated = client.patch(
            f"/api/v1/entries/{entry_id}",
            json={"payload": {"food": "Сухой корм", "amount": 260, "unit": "g"}},
        )
        assert updated.status_code == 200
        assert updated.json()["payload"]["amount"] == 260


def test_attachment_and_export() -> None:
    with TestClient(app) as client:
        pet_id = client.get("/api/v1/bootstrap").json()["pet"]["id"]
        entry_id = str(uuid4())
        client.post(
            "/api/v1/entries",
            json={
                "id": entry_id,
                "pet_id": pet_id,
                "type": "note",
                "occurred_at": datetime.now(UTC).isoformat(),
                "note": "Фото",
                "payload": {"title": "Вложение"},
            },
        )

        attachment_id = str(uuid4())
        uploaded = client.post(
            f"/api/v1/entries/{entry_id}/attachments",
            headers={"X-Attachment-ID": attachment_id},
            files={"file": ("nero.png", b"fake-png-content", "image/png")},
        )
        assert uploaded.status_code == 200
        repeated = client.post(
            f"/api/v1/entries/{entry_id}/attachments",
            headers={"X-Attachment-ID": attachment_id},
            files={"file": ("nero.png", b"fake-png-content", "image/png")},
        )
        assert repeated.status_code == 200
        assert repeated.json()["id"] == uploaded.json()["id"]
        attachment_url = uploaded.json()["url"]
        assert client.get(attachment_url).content == b"fake-png-content"

        exported = client.get("/api/v1/export")
        assert exported.status_code == 200
        with ZipFile(io.BytesIO(exported.content)) as archive:
            names = archive.namelist()
            assert "entries.json" in names
            assert "entries.csv" in names
            assert any(name.endswith("nero.png") for name in names)
