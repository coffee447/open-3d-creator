"""Command line interface for pcb2print3d."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import convert_kicad_to_stl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcb2print3d",
        description="Convert KiCad .kicad_pcb files into 3D-printable STL models.",
    )
    parser.add_argument("input", type=Path, help="Input KiCad PCB file (.kicad_pcb)")
    parser.add_argument("output", type=Path, help="Output STL file path")
    parser.add_argument(
        "--thickness-mm",
        type=float,
        default=1.6,
        help="PCB thickness in mm (default: 1.6)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = convert_kicad_to_stl(
        input_path=args.input,
        output_path=args.output,
        thickness_mm=args.thickness_mm,
    )

    print(f"Input:      {result.input_file}")
    print(f"Output:     {result.output_file}")
    print(f"Thickness:  {result.thickness_mm:.2f} mm")
    print(f"Outline:    {result.outline_points} points")
    print(f"Holes:      {result.holes}")
    print(f"Triangles:  {result.triangles}")


if __name__ == "__main__":
    main()
