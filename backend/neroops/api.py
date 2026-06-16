import csv
import io
import json
import zipfile
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from neroops.config import Settings, get_settings
from neroops.database import get_session
from neroops.models import Attachment, Entry, EntryType, Pet
from neroops.schemas import (
    AttachmentRead,
    BootstrapResponse,
    CatalogItem,
    EntryCreate,
    EntryPage,
    EntryRead,
    EntryUpdate,
    PetRead,
    PetUpdate,
    SummaryResponse,
    validate_payload,
)
from neroops.services.reports import build_summary
from neroops.services.storage import InvalidUpload, save_upload

router = APIRouter(prefix="/api/v1")
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

ENTRY_LABELS = {
    EntryType.feeding: "Кормление",
    EntryType.walk: "Прогулка",
    EntryType.symptom: "Симптом",
    EntryType.wellbeing: "Самочувствие",
    EntryType.training: "Тренировка",
    EntryType.medication: "Лекарство",
    EntryType.weight: "Вес",
    EntryType.vet_visit: "Ветеринар",
    EntryType.note: "Заметка",
}


def get_default_pet(session: Session) -> Pet:
    pet = session.scalar(select(Pet).order_by(Pet.created_at).limit(1))
    if pet is None:
        pet = Pet(name="Неро", species="dog", breed="Лабрадор")
        session.add(pet)
        session.commit()
        session.refresh(pet)
    return pet


def get_entry_or_404(session: Session, entry_id: str) -> Entry:
    entry = session.scalar(
        select(Entry).options(selectinload(Entry.attachments)).where(Entry.id == entry_id)
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(UTC).isoformat()}


@router.get("/bootstrap", response_model=BootstrapResponse)
def bootstrap(session: SessionDep) -> BootstrapResponse:
    pet = get_default_pet(session)
    recent = list(
        session.scalars(
            select(Entry)
            .options(selectinload(Entry.attachments))
            .where(Entry.pet_id == pet.id)
            .order_by(Entry.occurred_at.desc())
            .limit(100)
        )
    )
    return BootstrapResponse(
        pet=PetRead.model_validate(pet),
        entry_types=[
            CatalogItem(value=entry_type.value, label=ENTRY_LABELS[entry_type])
            for entry_type in EntryType
        ],
        recent_entries=[EntryRead.model_validate(entry) for entry in recent],
        server_time=datetime.now(UTC),
    )


@router.patch("/pet", response_model=PetRead)
def update_pet(payload: PetUpdate, session: SessionDep) -> Pet:
    pet = get_default_pet(session)
    for field, value in payload.model_dump().items():
        setattr(pet, field, value)
    session.commit()
    session.refresh(pet)
    return pet


@router.post("/entries", response_model=EntryRead)
def create_entry(payload: EntryCreate, session: SessionDep) -> Entry:
    existing = session.get(Entry, str(payload.id))
    if existing is not None:
        return get_entry_or_404(session, existing.id)

    pet = session.get(Pet, str(payload.pet_id))
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")

    entry = Entry(
        id=str(payload.id),
        pet_id=str(payload.pet_id),
        type=payload.type,
        occurred_at=payload.occurred_at,
        note=payload.note,
        payload=payload.payload,
    )
    session.add(entry)
    session.commit()
    return get_entry_or_404(session, entry.id)


@router.get("/entries", response_model=EntryPage)
def list_entries(
    session: SessionDep,
    settings: SettingsDep,
    entry_type: Annotated[EntryType | None, Query(alias="type")] = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EntryPage:
    pet = get_default_pet(session)
    filters = [Entry.pet_id == pet.id]
    if entry_type:
        filters.append(Entry.type == entry_type)
    if from_date:
        filters.append(Entry.occurred_at >= local_midnight_utc(from_date, settings.timezone))
    if to_date:
        filters.append(
            Entry.occurred_at < local_midnight_utc(to_date + timedelta(days=1), settings.timezone)
        )

    total = session.scalar(select(func.count(Entry.id)).where(*filters)) or 0
    entries = list(
        session.scalars(
            select(Entry)
            .options(selectinload(Entry.attachments))
            .where(*filters)
            .order_by(Entry.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return EntryPage(
        items=[EntryRead.model_validate(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/entries/{entry_id}", response_model=EntryRead)
def read_entry(entry_id: str, session: SessionDep) -> Entry:
    return get_entry_or_404(session, entry_id)


@router.patch("/entries/{entry_id}", response_model=EntryRead)
def update_entry(entry_id: str, payload: EntryUpdate, session: SessionDep) -> Entry:
    entry = get_entry_or_404(session, entry_id)
    changes = payload.model_dump(exclude_unset=True)
    if "payload" in changes:
        changes["payload"] = validate_payload(entry.type, changes["payload"])
    for field, value in changes.items():
        setattr(entry, field, value)
    session.commit()
    return get_entry_or_404(session, entry.id)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, session: SessionDep, settings: SettingsDep) -> None:
    entry = get_entry_or_404(session, entry_id)
    stored_names = [attachment.stored_name for attachment in entry.attachments]
    session.delete(entry)
    session.commit()
    for stored_name in stored_names:
        (settings.attachment_dir / stored_name).unlink(missing_ok=True)


@router.post("/entries/{entry_id}/attachments", response_model=AttachmentRead)
async def create_attachment(
    entry_id: str,
    session: SessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    attachment_id: Annotated[str | None, Header(alias="X-Attachment-ID")] = None,
) -> Attachment:
    entry = get_entry_or_404(session, entry_id)
    if attachment_id:
        existing = session.get(Attachment, attachment_id)
        if existing is not None:
            if existing.entry_id != entry.id:
                raise HTTPException(status_code=409, detail="Attachment ID already exists")
            return existing
    if len(entry.attachments) >= 5:
        raise HTTPException(status_code=400, detail="An entry can have at most 5 attachments")
    try:
        filename, stored_name, size, sha256 = await save_upload(file, settings.attachment_dir)
    except InvalidUpload as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    attachment = Attachment(
        id=attachment_id,
        entry_id=entry.id,
        filename=filename,
        stored_name=stored_name,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        sha256=sha256,
    )
    session.add(attachment)
    session.commit()
    session.refresh(attachment)
    return attachment


@router.get("/attachments/{attachment_id}")
def read_attachment(attachment_id: str, session: SessionDep, settings: SettingsDep) -> FileResponse:
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = settings.attachment_dir / attachment.stored_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(path, media_type=attachment.mime_type, filename=attachment.filename)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, session: SessionDep, settings: SettingsDep) -> None:
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    stored_name = attachment.stored_name
    session.delete(attachment)
    session.commit()
    (settings.attachment_dir / stored_name).unlink(missing_ok=True)


def local_midnight_utc(day: date, timezone_name: str) -> datetime:
    local_time = datetime.combine(day, time.min, tzinfo=ZoneInfo(timezone_name))
    return local_time.astimezone(UTC)


def date_range_query(
    session: Session,
    settings: Settings,
    from_date: date,
    to_date: date,
) -> list[Entry]:
    pet = get_default_pet(session)
    return list(
        session.scalars(
            select(Entry)
            .where(
                Entry.pet_id == pet.id,
                Entry.occurred_at >= local_midnight_utc(from_date, settings.timezone),
                Entry.occurred_at
                < local_midnight_utc(to_date + timedelta(days=1), settings.timezone),
            )
            .order_by(Entry.occurred_at)
        )
    )


@router.get("/dashboard/today", response_model=SummaryResponse)
def today_dashboard(session: SessionDep, settings: SettingsDep) -> SummaryResponse:
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    return build_summary(
        date_range_query(session, settings, today, today),
        today,
        today,
        settings.timezone,
    )


@router.get("/reports/summary", response_model=SummaryResponse)
def report_summary(
    session: SessionDep,
    settings: SettingsDep,
    from_date: Annotated[date, Query(alias="from")],
    to_date: Annotated[date, Query(alias="to")],
) -> SummaryResponse:
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="'to' must not be earlier than 'from'")
    if (to_date - from_date).days > 3660:
        raise HTTPException(status_code=400, detail="Date range is too large")
    return build_summary(
        date_range_query(session, settings, from_date, to_date),
        from_date,
        to_date,
        settings.timezone,
    )


@router.get("/export")
def export_data(session: SessionDep, settings: SettingsDep) -> StreamingResponse:
    pet = get_default_pet(session)
    entries = list(
        session.scalars(
            select(Entry)
            .options(selectinload(Entry.attachments))
            .where(Entry.pet_id == pet.id)
            .order_by(Entry.occurred_at)
        )
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "pet.json",
            json.dumps(
                PetRead.model_validate(pet).model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
        )
        archive.writestr(
            "entries.json",
            json.dumps(
                [EntryRead.model_validate(entry).model_dump(mode="json") for entry in entries],
                ensure_ascii=False,
                indent=2,
            ),
        )

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(
            csv_buffer,
            fieldnames=["id", "type", "occurred_at", "note", "payload"],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "id": entry.id,
                    "type": entry.type.value,
                    "occurred_at": entry.occurred_at.isoformat(),
                    "note": entry.note or "",
                    "payload": json.dumps(entry.payload, ensure_ascii=False),
                }
            )
        archive.writestr("entries.csv", csv_buffer.getvalue())

        for entry in entries:
            for attachment in entry.attachments:
                path = settings.attachment_dir / attachment.stored_name
                if path.exists():
                    archive.write(path, f"attachments/{entry.id}/{attachment.filename}")

    output.seek(0)
    filename = f"neroops-export-{date.today().isoformat()}.zip"
    return StreamingResponse(
        output,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
