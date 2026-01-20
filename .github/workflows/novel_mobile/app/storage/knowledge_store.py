from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.utils.paths import ensure_dir


@dataclass(frozen=True)
class KnowledgeBase:
    characters: list[str]
    places: list[str]


class KnowledgeStore:
    def __init__(self, project_dir: Path):
        self.dir = ensure_dir(project_dir / "knowledge")
        self.path = self.dir / "knowledge.json"
        if not self.path.exists():
            self.path.write_text(
                json.dumps(
                    {
                        "characters": ["主角", "反派", "导师"],
                        "places": ["王都", "黑森林", "旧港"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def load(self) -> KnowledgeBase:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            d = {"characters": [], "places": []}
        chars = [str(x) for x in (d.get("characters") or [])]
        places = [str(x) for x in (d.get("places") or [])]
        return KnowledgeBase(characters=chars, places=places)
