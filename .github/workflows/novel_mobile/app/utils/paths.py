from __future__ import annotations

import os
from pathlib import Path


def data_root() -> Path:
    """返回应用数据根目录。

    - 移动端/桌面统一：优先读环境变量 NOVEL_DATA_DIR（由 Kivy App 注入）。
    - 否则退化到当前工作目录下的 novel_mobile_data。
    """
    env = os.environ.get("NOVEL_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (Path(os.getcwd()).resolve() / "novel_mobile_data")


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
