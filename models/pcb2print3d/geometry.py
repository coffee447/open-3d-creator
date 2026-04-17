"""Geometry helpers for turning 2D PCB shapes into 3D mesh data."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
Triangle = tuple[Point3D, Point3D, Point3D]


@dataclass(frozen=True)
class CircleCutout:
    """Circular board cutout or drill hole."""

    center: Point2D
    radius: float


def polygon_area(points: list[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, current in enumerate(points):
        nxt = points[(idx + 1) % len(points)]
        area += current[0] * nxt[1] - nxt[0] * current[1]
    return area / 2.0


def ensure_ccw(points: list[Point2D]) -> list[Point2D]:
    return points if polygon_area(points) > 0 else list(reversed(points))


def point_in_triangle(p: Point2D, a: Point2D, b: Point2D, c: Point2D) -> bool:
    def sign(p1: Point2D, p2: Point2D, p3: Point2D) -> float:
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)

    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def triangulate_polygon(points: list[Point2D]) -> list[tuple[Point2D, Point2D, Point2D]]:
    """Triangulate a simple polygon using ear clipping."""
    vertices = ensure_ccw(points)
    if len(vertices) < 3:
        return []
    if len(vertices) == 3:
        return [(vertices[0], vertices[1], vertices[2])]

    indices = list(range(len(vertices)))
    triangles: list[tuple[Point2D, Point2D, Point2D]] = []

    safety_counter = 0
    while len(indices) > 3 and safety_counter < len(vertices) * len(vertices):
        safety_counter += 1
        ear_found = False

        for i in range(len(indices)):
            i_prev = indices[(i - 1) % len(indices)]
            i_curr = indices[i]
            i_next = indices[(i + 1) % len(indices)]

            prev_pt = vertices[i_prev]
            curr_pt = vertices[i_curr]
            next_pt = vertices[i_next]

            cross = (
                (curr_pt[0] - prev_pt[0]) * (next_pt[1] - curr_pt[1])
                - (curr_pt[1] - prev_pt[1]) * (next_pt[0] - curr_pt[0])
            )
            if cross <= 0:
                continue

            has_inside = False
            for j in indices:
                if j in (i_prev, i_curr, i_next):
                    continue
                if point_in_triangle(vertices[j], prev_pt, curr_pt, next_pt):
                    has_inside = True
                    break
            if has_inside:
                continue

            triangles.append((prev_pt, curr_pt, next_pt))
            del indices[i]
            ear_found = True
            break

        if not ear_found:
            break

    if len(indices) == 3:
        triangles.append((vertices[indices[0]], vertices[indices[1]], vertices[indices[2]]))

    return triangles


def norm(v: Point3D) -> float:
    return sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def normal_of(tri: Triangle) -> Point3D:
    a, b, c = tri
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = norm(n)
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (n[0] / length, n[1] / length, n[2] / length)
