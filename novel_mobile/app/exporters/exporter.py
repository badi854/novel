from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models import ChapterNode, Project
from app.storage.project_store import ProjectStore


@dataclass(frozen=True)
class ExportContext:
    project: Project
    store: ProjectStore


def iter_chapters_dfs(node: ChapterNode):
    for c in node.children:
        yield c
        if c.children:
            yield from iter_chapters_dfs(c)


def flatten_content(ctx: ExportContext) -> list[tuple[str, str, bool]]:
    out: list[tuple[str, str, bool]] = []
    for n in iter_chapters_dfs(ctx.project.root):
        if n.is_folder:
            out.append((n.title, "", True))
        else:
            out.append((n.title, ctx.store.read_chapter(n.id), False))
    return out


class Exporter:
    format_name: str = ""

    def export(self, ctx: ExportContext, out_path: Path) -> None:
        raise NotImplementedError
