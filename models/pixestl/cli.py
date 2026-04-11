from __future__ import annotations

from .args import parse_args
from .plate_generator import PlateGenerator


def main(argv: list[str] | None = None) -> int:
    gi = parse_args(argv)
    PlateGenerator().process(gi)
    return 0

