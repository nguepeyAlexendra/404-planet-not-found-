import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def write_manifest(directory: Path, source_id: str, data: dict) -> Path:
    """Un manifest JSON par traitement : source, URL, checksum, version, outils, date."""
    directory.mkdir(parents=True, exist_ok=True)
    body = {"source_id": source_id, "written_at": datetime.now(timezone.utc).isoformat(), **data}
    path = directory / f"{source_id}.manifest.json"
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path
