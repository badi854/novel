from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from app.constants import CHAPTERS_DIRNAME, PROJECT_META_FILENAME
from app.models import ChapterNode, Project, project_from_dict, project_to_dict
from app.utils.paths import ensure_dir


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ProjectStore:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.meta_path = project_dir / PROJECT_META_FILENAME
        self.chapters_dir = ensure_dir(project_dir / CHAPTERS_DIRNAME)

    def exists(self) -> bool:
        return self.meta_path.exists()

    def create_default(self, title: str) -> Project:
        pid = str(uuid.uuid4())
        root = ChapterNode(id="root", title="目录", is_folder=True, children=[])
        p = Project(id=pid, title=title, root=root, created_at=now_iso(), updated_at=now_iso())
        self.save(p)
        return p

    def load(self) -> Project:
        with self.meta_path.open("r", encoding="utf-8") as f:
            d = json.load(f)
        return project_from_dict(d)

    def save(self, p: Project) -> None:
        p2 = replace(p, updated_at=now_iso())
        with self.meta_path.open("w", encoding="utf-8") as f:
            json.dump(project_to_dict(p2), f, ensure_ascii=False, indent=2)

    def chapter_path(self, chapter_id: str) -> Path:
        return self.chapters_dir / f"{chapter_id}.md"

    def read_chapter(self, chapter_id: str) -> str:
        path = self.chapter_path(chapter_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_chapter(self, chapter_id: str, text: str) -> None:
        self.chapter_path(chapter_id).write_text(text or "", encoding="utf-8")
