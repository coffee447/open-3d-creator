from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .gen_instruction import ColorDistanceComputation


Rgb = tuple[int, int, int]


def transparent_pixel(argb: np.ndarray | int) -> bool:
    """Java equivalent: (pixel & 0xFF000000) == 0."""
    if isinstance(argb, int):
        return (argb & 0xFF000000) == 0
    return bool((int(argb) & 0xFF000000) == 0)


def has_transparent_neighbor(argb_img: np.ndarray, x: int, y: int) -> bool:
    h, w = argb_img.shape
    neighbors = ((x, y + 1), (x + 1, y), (x, y - 1), (x - 1, y))
    for xn, yn in neighbors:
        if xn < 0 or xn >= w or yn < 0 or yn >= h:
            return True
        if transparent_pixel(int(argb_img[yn, xn])):
            return True
    return False


def hex_to_rgb(hex_color: str) -> Rgb:
    s = hex_color.strip()
    if not (s.startswith("#") and len(s) == 7):
        raise ValueError(f"Incorrect color format: {hex_color}")
    r = int(s[1:3], 16)
    g = int(s[3:5], 16)
    b = int(s[5:7], 16)
    return (r, g, b)


def rgb_to_hex(rgb: Rgb) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def color_to_cmyk(rgb: Rgb) -> tuple[float, float, float, float]:
    r, g, b = rgb
    rr = r / 255.0
    gg = g / 255.0
    bb = b / 255.0
    k = 1.0 - max(rr, gg, bb)
    c = m = y = 0.0
    if k < 1.0:
        c = (1 - rr - k) / (1 - k)
        m = (1 - gg - k) / (1 - k)
        y = (1 - bb - k) / (1 - k)
    return (c, m, y, k)


def cmyk_to_rgb(c: float, m: float, y: float, k: float) -> Rgb:
    r = int((1 - c) * (1 - k) * 255)
    g = int((1 - m) * (1 - k) * 255)
    b = int((1 - y) * (1 - k) * 255)
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    return (r, g, b)


def hue_to_rgb(p: float, q: float, t: float) -> float:
    if t < 0:
        t += 1
    if t > 1:
        t -= 1
    if t < 1 / 6:
        return p + (q - p) * 6 * t
    if t < 1 / 2:
        return q
    if t < 2 / 3:
        return p + (q - p) * (2 / 3 - t) * 6
    return p


def hsl_to_cmyk(h: float, s: float, l: float) -> tuple[float, float, float, float]:
    # Mirrors Java logic in ColorUtil.hslToCmyk()
    s = s / 100.0
    l = l / 100.0
    if s == 0:
        return (0.0, 0.0, 0.0, 1.0 - l)

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    hk = h / 360.0

    r = hue_to_rgb(p, q, hk + 1 / 3)
    g = hue_to_rgb(p, q, hk)
    b = hue_to_rgb(p, q, hk - 1 / 3)

    c = 1 - r
    m = 1 - g
    y = 1 - b
    k = min(c, m, y)
    if k >= 1.0:
        return (0.0, 0.0, 0.0, 1.0)
    c = (c - k) / (1 - k)
    m = (m - k) / (1 - k)
    y = (y - k) / (1 - k)
    return (c, m, y, k)


def color_to_hsl(rgb: Rgb) -> tuple[float, float, float]:
    r, g, b = [c / 255.0 for c in rgb]
    mx = max(r, g, b)
    mn = min(r, g, b)
    lum = (mx + mn) / 2.0

    if mx == mn:
        sat = 0.0
        hue = 0.0
    else:
        delta = mx - mn
        sat = delta / (1 - abs(2 * lum - 1))
        if mx == r:
            hue = (60 * ((g - b) / (mx - mn)) + 360) % 360
        elif mx == g:
            hue = (60 * ((b - r) / (mx - mn)) + 120) % 360
        else:
            hue = (60 * ((r - g) / (mx - mn)) + 240) % 360

    return (hue, sat * 100.0, lum * 100.0)


def _pivot_rgb_to_xyz(n: float) -> float:
    return ((n + 0.055) / 1.055) ** 2.4 if n > 0.04045 else n / 12.92


def rgb_to_xyz(rgb: Rgb) -> tuple[float, float, float]:
    r, g, b = rgb
    rr = _pivot_rgb_to_xyz(r / 255.0)
    gg = _pivot_rgb_to_xyz(g / 255.0)
    bb = _pivot_rgb_to_xyz(b / 255.0)
    x = rr * 0.4124564 + gg * 0.3575761 + bb * 0.1804375
    y = rr * 0.2126729 + gg * 0.7151522 + bb * 0.0721750
    z = rr * 0.0193339 + gg * 0.1191920 + bb * 0.9503041
    return (x * 100.0, y * 100.0, z * 100.0)


def _pivot_xyz_to_lab(n: float) -> float:
    return n ** (1 / 3) if n > (6.0 / 29.0) ** 3 else (n / (3 * (6.0 / 29.0) ** 2)) + 4.0 / 29.0


def xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    x /= 95.047
    y /= 100.000
    z /= 108.883
    if x > 0:
        x = _pivot_xyz_to_lab(x)
    if y > 0:
        y = _pivot_xyz_to_lab(y)
    if z > 0:
        z = _pivot_xyz_to_lab(z)
    l = max(0.0, 116 * y - 16)
    a = (x - y) * 500
    b = (y - z) * 200
    return (l, a, b)


def rgb_to_lab(rgb: Rgb) -> tuple[float, float, float]:
    x, y, z = rgb_to_xyz(rgb)
    return xyz_to_lab(x, y, z)


def delta_e(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    dl = lab2[0] - lab1[0]
    da = lab2[1] - lab1[1]
    db = lab2[2] - lab1[2]
    return math.sqrt(dl * dl + da * da + db * db)


def find_closest_color(
    target_rgb: np.ndarray,
    palette_rgbs: np.ndarray,
    color_distance: ColorDistanceComputation,
    palette_lab: np.ndarray | None = None,
) -> int:
    """
    Return index of closest palette color for a single target pixel.
    Used for fallback; the main quantizer uses vectorized routines.
    """
    if color_distance == ColorDistanceComputation.RGB:
        d = palette_rgbs.astype(np.int32) - target_rgb.astype(np.int32)
        dist = np.sum(d * d, axis=1)
        return int(np.argmin(dist))
    # CIELab
    if palette_lab is None:
        palette_lab = np.array([rgb_to_lab(tuple(map(int, rgb))) for rgb in palette_rgbs], dtype=np.float64)
    tlab = np.array(rgb_to_lab(tuple(map(int, target_rgb))), dtype=np.float64)
    d = palette_lab - tlab
    dist = np.sqrt(np.sum(d * d, axis=1))
    return int(np.argmin(dist))


def hexcode_energy(hex_code: str) -> float:
    r, g, b = hex_to_rgb(hex_code)
    return float(r + g + b)


def rgb_energy(rgb: Rgb) -> float:
    r, g, b = rgb
    return float(r + g + b)


def k_of_hex(hex_code: str) -> float:
    return color_to_cmyk(hex_to_rgb(hex_code))[3]


def k_of_rgb(rgb: Rgb) -> float:
    return color_to_cmyk(rgb)[3]


def rgb_to_lab_array(rgb_uint8: np.ndarray) -> np.ndarray:
    """
    Vectorized sRGB uint8 -> CIELab (D65) conversion matching the Java formulas.
    Input shape: (..., 3), dtype uint8/float.
    Output shape: (..., 3), dtype float64.
    """
    arr = np.asarray(rgb_uint8, dtype=np.float64) / 255.0

    # pivotRgbToXyz
    lin = np.where(arr > 0.04045, ((arr + 0.055) / 1.055) ** 2.4, arr / 12.92)
    r = lin[..., 0]
    g = lin[..., 1]
    b = lin[..., 2]

    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    # xyzToLab
    x = (x * 100.0) / 95.047
    y = (y * 100.0) / 100.000
    z = (z * 100.0) / 108.883

    t = (6.0 / 29.0) ** 3
    a = 1.0 / 3.0
    def _pivot(n: np.ndarray) -> np.ndarray:
        return np.where(n > t, n**a, (n / (3 * (6.0 / 29.0) ** 2)) + 4.0 / 29.0)

    fx = _pivot(np.maximum(x, 0))
    fy = _pivot(np.maximum(y, 0))
    fz = _pivot(np.maximum(z, 0))

    L = np.maximum(0.0, 116 * fy - 16)
    A = (fx - fy) * 500
    B = (fy - fz) * 200

    return np.stack([L, A, B], axis=-1)

