from __future__ import annotations

import re
from dataclasses import dataclass


_WORD_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


def word_count(text: str) -> int:
    """近似“字数”：中文按字、英文按词。"""
    return len(_WORD_RE.findall(text or ""))


@dataclass(frozen=True)
class TempColor:
    bg: str
    fg: str


def lerp(a: int, b: int, t: float) -> int:
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return int(round(a + (b - a) * t))


def mix_rgb(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def temperature_to_colors(temp: int, mode: str) -> TempColor:
    temp = max(1000, min(9000, int(temp)))
    t = (temp - 1000) / 8000.0

    if mode == "night":
        warm = (22, 24, 28)
        cool = (18, 22, 30)
        bg = mix_rgb(warm, cool, t)
        fg = (232, 234, 237)
    elif mode == "eye":
        warm = (244, 237, 226)
        cool = (232, 242, 255)
        bg = mix_rgb(warm, cool, t)
        fg = (35, 38, 41)
    else:
        warm = (255, 250, 244)
        cool = (245, 250, 255)
        bg = mix_rgb(warm, cool, t)
        fg = (25, 28, 31)

    return TempColor(bg=rgb_to_hex(bg), fg=rgb_to_hex(fg))


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    s = (hex_color or "").lstrip("#")
    if len(s) != 6:
        return (0, 0, 0, alpha)
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    a = max(0.0, min(1.0, float(alpha)))
    return (r, g, b, a)
