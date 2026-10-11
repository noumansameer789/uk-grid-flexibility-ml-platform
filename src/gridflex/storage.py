"""Crash-safe local/shared-volume publication; readers never see a partial JSON file."""

import json
import os
import tempfile
import time
from pathlib import Path


class StorageUnavailable(RuntimeError):
    pass


def atomic_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise StorageUnavailable(f"Cannot publish {path.name}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    try:
        result = json.loads(path.read_text())
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        return result
    except (OSError, ValueError) as exc:
        raise StorageUnavailable(f"Cannot read {path.name}") from exc


def first_json(path: Path, payload: dict) -> dict:
    """Publish once across processes; always return the canonical stored version.

    Directory creation provides an exclusive lock without requiring hard links.
    A lock abandoned after a crash fails closed; an operator must inspect it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    deadline = time.monotonic() + 3
    while True:
        if path.exists():
            return read_json(path)
        try:
            lock.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise StorageUnavailable(f"Publication lock is busy: {path.name}") from None
            time.sleep(0.02)
        except OSError as exc:
            raise StorageUnavailable(f"Cannot lock {path.name}") from exc
    try:
        if path.exists():
            return read_json(path)
        atomic_text(path, json.dumps(payload, indent=2, allow_nan=False))
        return payload
    finally:
        lock.rmdir()
