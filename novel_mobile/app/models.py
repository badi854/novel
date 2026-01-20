from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChapterNode:
    id: str
    title: str
    is_folder: bool = False
    children: list["ChapterNode"] = field(default_factory=list)


@dataclass
class Project:
    id: str
    title: str
    root: ChapterNode
    created_at: str
    updated_at: str


def chapter_to_dict(node: ChapterNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "title": node.title,
        "is_folder": node.is_folder,
        "children": [chapter_to_dict(c) for c in node.children],
    }


def chapter_from_dict(d: dict[str, Any]) -> ChapterNode:
    return ChapterNode(
        id=str(d.get("id")),
        title=str(d.get("title", "未命名")),
        is_folder=bool(d.get("is_folder", False)),
        children=[chapter_from_dict(x) for x in (d.get("children") or [])],
    )


def project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "title": p.title,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "root": chapter_to_dict(p.root),
    }


def project_from_dict(d: dict[str, Any]) -> Project:
    return Project(
        id=str(d.get("id")),
        title=str(d.get("title", "我的小说")),
        created_at=str(d.get("created_at", "")),
        updated_at=str(d.get("updated_at", "")),
        root=chapter_from_dict(d.get("root") or {"id": "root", "title": "目录", "is_folder": True, "children": []}),
    )
