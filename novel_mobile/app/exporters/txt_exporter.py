from __future__ import annotations

from pathlib import Path

from app.exporters.exporter import ExportContext, Exporter, flatten_content


class TxtExporter(Exporter):
    format_name = "txt"

    def export(self, ctx: ExportContext, out_path: Path) -> None:
        parts: list[str] = []
        for title, text, is_folder in flatten_content(ctx):
            if is_folder:
                parts.append(f"\n# {title}\n")
                continue
            parts.append(f"\n## {title}\n")
            parts.append((text or "").rstrip() + "\n")
        out_path.write_text("\n".join(parts).lstrip(), encoding="utf-8")
