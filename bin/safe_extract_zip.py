#!/usr/bin/env python3
"""Extract a ZIP archive without following archive paths or symlinks.

Used by the npm CLI before installing the downloaded project source. The
archive is expected to be a GitHub source ZIP, but extraction still treats
all archive entries as untrusted input.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path

MAX_ENTRIES = 20_000
MAX_SINGLE_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000
MAX_PATH_PARTS = 128
MAX_PATH_LENGTH = 4_096

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _safe_parts(filename: str) -> tuple[tuple[str, ...], bool]:
    if not filename or "\x00" in filename:
        raise ValueError("ZIP entry has an empty name or NUL byte")

    # ZIP uses '/', but reject Windows/UNC/drive paths after normalizing
    # backslashes as separators so the same archive is safe on both OSes.
    normalized = filename.replace("\\", "/")
    if (
        normalized.startswith("/")
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise ValueError(f"Absolute ZIP path is not allowed: {filename!r}")

    is_directory = normalized.endswith("/")
    raw_parts = normalized.rstrip("/").split("/")
    if (
        not raw_parts
        or len(normalized) > MAX_PATH_LENGTH
        or len(raw_parts) > MAX_PATH_PARTS
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise ValueError(f"Unsafe ZIP path: {filename!r}")

    for part in raw_parts:
        if any(ord(char) < 32 for char in part):
            raise ValueError(f"Control character in ZIP path: {filename!r}")
        if any(char in '<>:"|?*' for char in part):
            raise ValueError(f"Windows-special character in ZIP path: {filename!r}")
        if part.endswith((" ", ".")):
            raise ValueError(f"Windows-ambiguous path component: {filename!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise ValueError(f"Windows-reserved path component: {filename!r}")

    return tuple(raw_parts), is_directory


def _ensure_directory(root: Path, parts: tuple[str, ...]) -> Path:
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing to traverse a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"ZIP path conflicts with a non-directory: {current}")
        current.mkdir(exist_ok=True)
    return current


def extract_safely(archive: Path, destination: Path) -> int:
    archive = archive.resolve(strict=True)
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve(strict=True)

    if any(destination.iterdir()):
        raise ValueError("Extraction destination must be empty")

    seen_names: set[str] = set()
    total_uncompressed = 0
    extracted = 0

    with zipfile.ZipFile(archive, "r") as zip_file:
        entries = zip_file.infolist()
        if not entries or len(entries) > MAX_ENTRIES:
            raise ValueError(f"Unexpected ZIP entry count: {len(entries)}")

        for entry in entries:
            parts, named_directory = _safe_parts(entry.filename)
            normalized_key = os.path.normcase("/".join(parts))
            if normalized_key in seen_names:
                raise ValueError(f"Duplicate ZIP path: {entry.filename!r}")
            seen_names.add(normalized_key)

            mode = entry.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            if file_type == stat.S_IFLNK:
                raise ValueError(f"Symlink entries are not allowed: {entry.filename!r}")
            if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError(f"Special file entry is not allowed: {entry.filename!r}")
            if entry.flag_bits & 0x1:
                raise ValueError(f"Encrypted ZIP entry is not supported: {entry.filename!r}")
            if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise ValueError(f"Unsupported ZIP compression: {entry.filename!r}")

            is_directory = named_directory or entry.is_dir() or file_type == stat.S_IFDIR
            if is_directory:
                if entry.file_size != 0:
                    raise ValueError(f"Directory entry contains data: {entry.filename!r}")
                _ensure_directory(destination, parts)
                extracted += 1
                continue

            if entry.file_size < 0 or entry.file_size > MAX_SINGLE_FILE_BYTES:
                raise ValueError(f"ZIP file exceeds the per-file size limit: {entry.filename!r}")
            total_uncompressed += entry.file_size
            if total_uncompressed > MAX_TOTAL_BYTES:
                raise ValueError("ZIP archive exceeds the total uncompressed size limit")
            if entry.file_size and (
                entry.compress_size <= 0
                or entry.file_size / entry.compress_size > MAX_COMPRESSION_RATIO
            ):
                raise ValueError(f"ZIP compression ratio is too high: {entry.filename!r}")

            parent = _ensure_directory(destination, parts[:-1])
            target = parent / parts[-1]
            resolved_target = target.resolve()
            if not resolved_target.is_relative_to(destination):
                raise ValueError(f"ZIP path escapes extraction root: {entry.filename!r}")
            if target.is_symlink() or target.exists():
                raise ValueError(f"ZIP entry would overwrite an existing path: {entry.filename!r}")

            written = 0
            try:
                with zip_file.open(entry, "r") as source, target.open("xb") as output:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > entry.file_size or written > MAX_SINGLE_FILE_BYTES:
                            raise ValueError(f"ZIP entry expanded beyond its declared size: {entry.filename!r}")
                        output.write(chunk)

                if written != entry.file_size:
                    raise ValueError(f"ZIP entry size mismatch: {entry.filename!r}")
                target.chmod(0o644)
            except Exception:
                target.unlink(missing_ok=True)
                raise

            extracted += 1

    return extracted


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: safe_extract_zip.py ARCHIVE.zip DESTINATION", file=sys.stderr)
        return 2

    try:
        count = extract_safely(Path(sys.argv[1]), Path(sys.argv[2]))
        print(f"Extracted {count} ZIP entries safely.")
        return 0
    except Exception as exc:
        print(f"Safe ZIP extraction failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
