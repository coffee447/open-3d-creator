"""Mesh generation and STL writing."""

from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

from .geometry import CircleCutout, Point2D, Point3D, Triangle, normal_of, triangulate_polygon


def _hole_segments(radius: float) -> int:
    if radius < 0.25:
        return 12
    if radius < 0.75:
        return 18
    return 24


def _distance(a: Point2D, b: Point2D) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def point_in_circle(point: Point2D, hole: CircleCutout, margin: float = 1e-5) -> bool:
    return _distance(point, hole.center) <= hole.radius + margin


def build_pcb_mesh(outline: list[Point2D], holes: list[CircleCutout], thickness: float) -> list[Triangle]:
    if thickness <= 0:
        raise ValueError("thickness must be > 0")
    if len(outline) < 3:
        raise ValueError("outline requires at least 3 points")

    z0 = 0.0
    z1 = thickness
    mesh: list[Triangle] = []

    # Top and bottom surfaces are triangulated from the outer polygon.
    # Any triangle touching a hole center is skipped as a lightweight cutout approximation.
    for a, b, c in triangulate_polygon(outline):
        centroid = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0)
        if any(point_in_circle(centroid, h) for h in holes):
            continue

        mesh.append(((a[0], a[1], z1), (b[0], b[1], z1), (c[0], c[1], z1)))
        mesh.append(((c[0], c[1], z0), (b[0], b[1], z0), (a[0], a[1], z0)))

    # Outer wall
    for i, p1 in enumerate(outline):
        p2 = outline[(i + 1) % len(outline)]
        v1: Point3D = (p1[0], p1[1], z0)
        v2: Point3D = (p2[0], p2[1], z0)
        v3: Point3D = (p2[0], p2[1], z1)
        v4: Point3D = (p1[0], p1[1], z1)
        mesh.append((v1, v2, v3))
        mesh.append((v1, v3, v4))

    # Cylindrical hole walls
    for hole in holes:
        segments = _hole_segments(hole.radius)
        ring_bottom: list[Point3D] = []
        ring_top: list[Point3D] = []
        for i in range(segments):
            angle = 2 * pi * i / segments
            x = hole.center[0] + hole.radius * cos(angle)
            y = hole.center[1] + hole.radius * sin(angle)
            ring_bottom.append((x, y, z0))
            ring_top.append((x, y, z1))

        for i in range(segments):
            n = (i + 1) % segments
            b1 = ring_bottom[i]
            b2 = ring_bottom[n]
            t2 = ring_top[n]
            t1 = ring_top[i]
            mesh.append((b1, t2, b2))
            mesh.append((b1, t1, t2))

    return mesh


def write_ascii_stl(path: Path, triangles: list[Triangle], solid_name: str = "pcb") -> None:
    lines = [f"solid {solid_name}"]
    for tri in triangles:
        nx, ny, nz = normal_of(tri)
        lines.append(f"  facet normal {nx:.6f} {ny:.6f} {nz:.6f}")
        lines.append("    outer loop")
        for vx, vy, vz in tri:
            lines.append(f"      vertex {vx:.6f} {vy:.6f} {vz:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
