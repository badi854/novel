from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.constants import VERSIONS_DIRNAME
from app.utils.paths import ensure_dir


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class VersionEntry:
    id: str
    chapter_id: str
    created_at: str
    rel_path: str
    word_count: int


class VersionStore:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.versions_dir = ensure_dir(project_dir / VERSIONS_DIRNAME)
        self.index_path = self.versions_dir / "versions.json"
        if not self.index_path.exists():
            self.index_path.write_text("[]", encoding="utf-8")

    def _load_index(self) -> list[dict]:
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []

    def _save_index(self, rows: list[dict]) -> None:
        self.index_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_versions(self, chapter_id: str) -> list[VersionEntry]:
        rows = [r for r in self._load_index() if r.get("chapter_id") == chapter_id]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return [VersionEntry(**r) for r in rows]

    def snapshot(self, chapter_id: str, content: str, word_count: int) -> VersionEntry:
        vid = str(uuid.uuid4())
        created_at = now_iso()
        ensure_dir(self.versions_dir / chapter_id)
        rel_path = str(Path(chapter_id) / f"{created_at.replace(':', '-')}_{vid}.md")
        abs_path = self.versions_dir / rel_path
        abs_path.write_text(content or "", encoding="utf-8")

        entry = VersionEntry(id=vid, chapter_id=chapter_id, created_at=created_at, rel_path=rel_path, word_count=int(word_count))
        rows = self._load_index()
        rows.append(entry.__dict__)
        self._save_index(rows)
        return entry

    def read_version(self, entry: VersionEntry) -> str:
        p = self.versions_dir / entry.rel_path
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")
