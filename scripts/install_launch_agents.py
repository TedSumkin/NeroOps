#!/usr/bin/env python3
import argparse
import os
import plistlib
import subprocess
from pathlib import Path

SERVER_LABEL = "com.neroops.server"
BACKUP_LABEL = "com.neroops.backup"


def launchctl(*arguments: str, check: bool = True) -> None:
    subprocess.run(["launchctl", *arguments], check=check)


def write_plist(path: Path, payload: dict) -> None:
    with path.open("wb") as output:
        plistlib.dump(payload, output, sort_keys=False)


def uninstall(agent_dir: Path) -> None:
    domain = f"gui/{os.getuid()}"
    for label in (SERVER_LABEL, BACKUP_LABEL):
        path = agent_dir / f"{label}.plist"
        launchctl("bootout", domain, str(path), check=False)
        path.unlink(missing_ok=True)
    print("NeroOps launch agents removed")


def install(project_dir: Path, agent_dir: Path) -> None:
    python = project_dir / ".venv" / "bin" / "python"
    uvicorn = project_dir / ".venv" / "bin" / "uvicorn"
    frontend = project_dir / "frontend" / "dist" / "index.html"
    if not python.exists() or not uvicorn.exists():
        raise SystemExit("Run `make install` first")
    if not frontend.exists():
        raise SystemExit("Run `make build` first")

    data_dir = project_dir / "data"
    backup_dir = project_dir / "backups"
    log_dir = project_dir / "logs"
    for directory in (data_dir, backup_dir, log_dir, agent_dir):
        directory.mkdir(parents=True, exist_ok=True)

    common_environment = {
        "NEROOPS_DATA_DIR": str(data_dir),
        "NEROOPS_TIMEZONE": "Europe/Moscow",
    }
    server_plist = agent_dir / f"{SERVER_LABEL}.plist"
    backup_plist = agent_dir / f"{BACKUP_LABEL}.plist"

    write_plist(
        server_plist,
        {
            "Label": SERVER_LABEL,
            "ProgramArguments": [
                str(uvicorn),
                "neroops.main:app",
                "--app-dir",
                "backend",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            "WorkingDirectory": str(project_dir),
            "EnvironmentVariables": common_environment,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Background",
            "StandardOutPath": str(log_dir / "server.log"),
            "StandardErrorPath": str(log_dir / "server-error.log"),
        },
    )
    write_plist(
        backup_plist,
        {
            "Label": BACKUP_LABEL,
            "ProgramArguments": [
                str(python),
                str(project_dir / "scripts" / "backup.py"),
                "--data-dir",
                str(data_dir),
                "--output-dir",
                str(backup_dir),
            ],
            "WorkingDirectory": str(project_dir),
            "StartCalendarInterval": {"Hour": 3, "Minute": 15},
            "StandardOutPath": str(log_dir / "backup.log"),
            "StandardErrorPath": str(log_dir / "backup-error.log"),
        },
    )

    domain = f"gui/{os.getuid()}"
    for path in (server_plist, backup_plist):
        launchctl("bootout", domain, str(path), check=False)
        launchctl("bootstrap", domain, str(path))
    print("NeroOps server and daily backup launch agents installed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage NeroOps launchd agents")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    agent_dir = Path.home() / "Library" / "LaunchAgents"
    if args.uninstall:
        uninstall(agent_dir)
    else:
        install(project_dir, agent_dir)


if __name__ == "__main__":
    main()
