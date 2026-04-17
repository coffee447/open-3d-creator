"""Minimal KiCad PCB parser for board outline and drill holes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .geometry import CircleCutout, Point2D


EDGE_LINE_RE = re.compile(
    r"\(gr_line\s+\(start\s+([\-0-9.]+)\s+([\-0-9.]+)\)\s+\(end\s+([\-0-9.]+)\s+([\-0-9.]+)\).*?\(layer\s+\"?Edge\.Cuts\"?\)",
    re.IGNORECASE,
)
AT_RE = re.compile(r"\(at\s+([\-0-9.]+)\s+([\-0-9.]+)")
DRILL_RE = re.compile(r"\(drill\s+([0-9.]+)")


@dataclass(frozen=True)
class PcbData:
    outline: list[Point2D]
    holes: list[CircleCutout]


def _extract_pad_blocks(file_content: str) -> list[str]:
    blocks: list[str] = []
    idx = 0
    while True:
        start = file_content.find("(pad", idx)
        if start < 0:
            break
        depth = 0
        end = start
        for pos in range(start, len(file_content)):
            char = file_content[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = pos + 1
                    break
        if end <= start:
            break
        blocks.append(file_content[start:end])
        idx = end
    return blocks


def _ordered_outline(lines: list[tuple[Point2D, Point2D]], tolerance: float = 1e-6) -> list[Point2D]:
    if not lines:
        raise ValueError("No Edge.Cuts line segments found in input.")

    chain = [lines[0][0], lines[0][1]]
    unused = lines[1:]

    def close_enough(a: Point2D, b: Point2D) -> bool:
        return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance

    while unused:
        tail = chain[-1]
        next_idx = -1
        append_point: Point2D | None = None
        for idx, (a, b) in enumerate(unused):
            if close_enough(a, tail):
                next_idx = idx
                append_point = b
                break
            if close_enough(b, tail):
                next_idx = idx
                append_point = a
                break

        if next_idx < 0 or append_point is None:
            raise ValueError("Edge.Cuts segments do not form a single closed chain.")

        chain.append(append_point)
        del unused[next_idx]

    if close_enough(chain[-1], chain[0]):
        chain.pop()

    return chain


def parse_kicad_pcb(file_content: str) -> PcbData:
    lines: list[tuple[Point2D, Point2D]] = []
    for match in EDGE_LINE_RE.finditer(file_content):
        x1, y1, x2, y2 = map(float, match.groups())
        lines.append(((x1, y1), (x2, y2)))

    outline = _ordered_outline(lines)

    holes: list[CircleCutout] = []
    for block in _extract_pad_blocks(file_content):
        at_match = AT_RE.search(block)
        drill_match = DRILL_RE.search(block)
        if not at_match or not drill_match:
            continue

        x, y = map(float, at_match.groups())
        drill_dia = float(drill_match.group(1))
        holes.append(CircleCutout(center=(x, y), radius=drill_dia / 2.0))

    return PcbData(outline=outline, holes=holes)
