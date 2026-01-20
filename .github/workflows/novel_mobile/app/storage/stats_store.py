from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.constants import STATS_DIRNAME
from app.utils.paths import ensure_dir


def today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


class StatsStore:
    def __init__(self, project_dir: Path):
        self.stats_dir = ensure_dir(project_dir / STATS_DIRNAME)
        self.path = self.stats_dir / "word_history.json"
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def append_total(self, total_words: int, ts: str) -> None:
        rows = self.load_history_raw()
        rows.append({"ts": ts, "total_words": int(total_words)})
        if len(rows) > 20000:
            rows = rows[-20000:]
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_history_raw(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except Exception:
            return []

    def daily_progress(self) -> dict[str, int]:
        rows = self.load_history_raw()
        by_day: dict[str, list[int]] = {}
        for r in rows:
            ts = str(r.get("ts", ""))
            day = ts[:10] if len(ts) >= 10 else ""
            if not day:
                continue
            by_day.setdefault(day, []).append(int(r.get("total_words", 0)))

        out: dict[str, int] = {}
        for day, vals in by_day.items():
            if not vals:
                continue
            out[day] = max(vals) - min(vals)
        return out
