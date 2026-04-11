from __future__ import annotations

import math
from typing import BinaryIO


def _normal(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> tuple[float, float, float]:
    ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln == 0:
        return (0.0, 0.0, 0.0)
    return (nx / ln, ny / ln, nz / ln)


def solid_begin(f: BinaryIO, name: str) -> None:
    f.write(f"solid {name}\n".encode("ascii", errors="ignore"))


def solid_end(f: BinaryIO, name: str) -> None:
    f.write(f"endsolid {name}\n".encode("ascii", errors="ignore"))


def facet(f: BinaryIO, a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> None:
    nx, ny, nz = _normal(a, b, c)
    f.write(f"  facet normal {nx:.8e} {ny:.8e} {nz:.8e}\n".encode("ascii"))
    f.write(b"    outer loop\n")
    f.write(f"      vertex {a[0]:.8e} {a[1]:.8e} {a[2]:.8e}\n".encode("ascii"))
    f.write(f"      vertex {b[0]:.8e} {b[1]:.8e} {b[2]:.8e}\n".encode("ascii"))
    f.write(f"      vertex {c[0]:.8e} {c[1]:.8e} {c[2]:.8e}\n".encode("ascii"))
    f.write(b"    endloop\n")
    f.write(b"  endfacet\n")


def cube(
    f: BinaryIO,
    cx: float,
    cy: float,
    cz: float,
    sx: float,
    sy: float,
    sz: float,
) -> None:
    hx = sx / 2.0
    hy = sy / 2.0
    hz = sz / 2.0

    # 8 vertices
    v000 = (cx - hx, cy - hy, cz - hz)
    v001 = (cx - hx, cy - hy, cz + hz)
    v010 = (cx - hx, cy + hy, cz - hz)
    v011 = (cx - hx, cy + hy, cz + hz)
    v100 = (cx + hx, cy - hy, cz - hz)
    v101 = (cx + hx, cy - hy, cz + hz)
    v110 = (cx + hx, cy + hy, cz - hz)
    v111 = (cx + hx, cy + hy, cz + hz)

    # Faces (two triangles each), outward winding
    # -X
    facet(f, v000, v010, v011)
    facet(f, v000, v011, v001)
    # +X
    facet(f, v100, v101, v111)
    facet(f, v100, v111, v110)
    # -Y
    facet(f, v000, v001, v101)
    facet(f, v000, v101, v100)
    # +Y
    facet(f, v010, v110, v111)
    facet(f, v010, v111, v011)
    # -Z
    facet(f, v000, v100, v110)
    facet(f, v000, v110, v010)
    # +Z
    facet(f, v001, v011, v111)
    facet(f, v001, v111, v101)

