#!/usr/bin/env python3
import argparse
import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


def backup(data_dir: Path, output_dir: Path) -> Path:
    database = data_dir / "neroops.sqlite3"
    if not database.exists():
        raise FileNotFoundError(f"Database does not exist: {database}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"neroops-backup-{timestamp}.zip"

    with tempfile.TemporaryDirectory(prefix="neroops-backup-") as temporary:
        database_copy = Path(temporary) / "neroops.sqlite3"
        with sqlite3.connect(database) as source, sqlite3.connect(database_copy) as target:
            source.backup(target)

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(database_copy, "neroops.sqlite3")
            attachments = data_dir / "attachments"
            if attachments.exists():
                for path in attachments.rglob("*"):
                    if path.is_file():
                        archive.write(path, Path("attachments") / path.relative_to(attachments))
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "created_at": datetime.now(UTC).isoformat(),
                        "format_version": 1,
                    },
                    indent=2,
                ),
            )

    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent NeroOps backup")
    parser.add_argument("--data-dir", type=Path, default=Path("./data"))
    parser.add_argument("--output-dir", type=Path, default=Path("./backups"))
    args = parser.parse_args()
    destination = backup(args.data_dir, args.output_dir)
    print(destination)


if __name__ == "__main__":
    main()
