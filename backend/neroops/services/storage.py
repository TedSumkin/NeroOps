import hashlib
import re
import uuid
from pathlib import Path

from fastapi import UploadFile

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}
MAX_FILE_SIZE = 12 * 1024 * 1024


class InvalidUpload(ValueError):
    pass


def safe_filename(filename: str | None) -> str:
    candidate = Path(filename or "attachment").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
    return cleaned[:200] or "attachment"


async def save_upload(upload: UploadFile, directory: Path) -> tuple[str, str, int, str]:
    mime_type = upload.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_MIME_TYPES:
        raise InvalidUpload("Unsupported file type")

    original_name = safe_filename(upload.filename)
    extension = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4()}{extension}"
    target = directory / stored_name
    digest = hashlib.sha256()
    size = 0

    try:
        with target.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise InvalidUpload("File is larger than 12 MB")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return original_name, stored_name, size, digest.hexdigest()
