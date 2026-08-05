#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills/session-token-monitor"
OUTPUT = ROOT / "dist/session-token-monitor.skill"
ARCHIVE_PREFIX = "session-token-monitor"
EXCLUDED_NAMES = {".DS_Store"}


def normalized_archive_mode(mode: int) -> int:
    return 0o755 if mode & 0o111 else 0o644


def source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name not in EXCLUDED_NAMES
        and not path.name.endswith((".pyc", ".pyo"))
    )


def member_name(path: Path) -> str:
    return f"{ARCHIVE_PREFIX}/{path.relative_to(SOURCE).as_posix()}"


def build(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files():
            info = zipfile.ZipInfo(member_name(path), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = normalized_archive_mode(path.stat().st_mode) << 16
            archive.writestr(info, path.read_bytes())


def archive_manifest(path: Path) -> dict[str, tuple[bytes, int]]:
    with zipfile.ZipFile(path, "r") as archive:
        manifest: dict[str, tuple[bytes, int]] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            if info.filename in manifest:
                raise ValueError(f"duplicate archive member: {info.filename}")
            mode = normalized_archive_mode(info.external_attr >> 16)
            manifest[info.filename] = (archive.read(info), mode)
        return manifest


def expected_manifest() -> dict[str, tuple[bytes, int]]:
    return {
        member_name(path): (path.read_bytes(), normalized_archive_mode(path.stat().st_mode))
        for path in source_files()
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the packaged session-token-monitor skill.")
    parser.add_argument("--check", action="store_true", help="Verify logical artifact contents without rewriting it")
    args = parser.parse_args()

    if args.check:
        if not OUTPUT.exists() or archive_manifest(OUTPUT) != expected_manifest():
            raise SystemExit("dist/session-token-monitor.skill is stale; rebuild it")
        print(f"PASS skill archive matches {len(source_files())} source files")
        return 0

    fd, temporary_name = tempfile.mkstemp(prefix=".session-token-monitor.", suffix=".skill", dir=OUTPUT.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        build(temporary)
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"built {OUTPUT.relative_to(ROOT)} with {len(source_files())} source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
