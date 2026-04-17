"""End-to-end conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .kicad_parser import parse_kicad_pcb
from .mesh import build_pcb_mesh, write_ascii_stl


@dataclass(frozen=True)
class ConversionResult:
    input_file: Path
    output_file: Path
    outline_points: int
    holes: int
    triangles: int
    thickness_mm: float


def convert_kicad_to_stl(input_path: Path, output_path: Path, thickness_mm: float = 1.6) -> ConversionResult:
    content = input_path.read_text(encoding="utf-8")
    pcb = parse_kicad_pcb(content)
    mesh = build_pcb_mesh(outline=pcb.outline, holes=pcb.holes, thickness=thickness_mm)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_ascii_stl(output_path, mesh, solid_name=input_path.stem)
    return ConversionResult(
        input_file=input_path,
        output_file=output_path,
        outline_points=len(pcb.outline),
        holes=len(pcb.holes),
        triangles=len(mesh),
        thickness_mm=thickness_mm,
    )
