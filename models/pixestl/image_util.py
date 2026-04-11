from __future__ import annotations

import math

import numpy as np
from PIL import Image


def check_ratio(image: Image.Image, image_width_mm: float, image_height_mm: float) -> None:
    if image_width_mm == 0 or image_height_mm == 0:
        return
    w, h = image.size
    ratio_src = w / h
    ratio_dest = image_width_mm / image_height_mm
    # Mirror Java's 2-decimal formatted compare
    if f"{ratio_src:.2f}" != f"{ratio_dest:.2f}":
        print(f"Warning : The image ratio is not preserved. (Source ratio:{ratio_src:.2f}; Destination ratio:{ratio_dest:.2f})")


def resize_image(image: Image.Image, image_width_mm: float, image_height_mm: float, pixel_mm: float) -> Image.Image:
    w, h = image.size

    if image_width_mm != 0 and image_height_mm == 0:
        nb_pixel_width = int(image_width_mm / pixel_mm)
        height_mm = int(h * image_width_mm / w)
        nb_pixel_height = int(height_mm / pixel_mm)
    elif image_width_mm == 0 and image_height_mm != 0:
        nb_pixel_height = int(image_height_mm / pixel_mm)
        width_mm = int(w * image_height_mm / h)
        nb_pixel_width = int(width_mm / pixel_mm)
    else:
        nb_pixel_width = int(image_width_mm / pixel_mm)
        nb_pixel_height = int(image_height_mm / pixel_mm)

    nb_pixel_width = max(1, nb_pixel_width)
    nb_pixel_height = max(1, nb_pixel_height)

    # Java uses drawImage => nearest-ish by default; use bilinear for smoother, it’s fine for quantization.
    return image.resize((nb_pixel_width, nb_pixel_height), resample=Image.BILINEAR)


def has_transparency(image: Image.Image) -> bool:
    if image.mode in ("RGBA", "LA"):
        alpha = image.getchannel("A")
        return np.any(np.array(alpha, dtype=np.uint8) == 0)
    return False


def convert_to_black_and_white(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    arr = np.array(rgba, dtype=np.uint8)
    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]
    lum = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]).astype(np.uint8)
    out = np.zeros_like(arr)
    out[:, :, 0] = lum
    out[:, :, 1] = lum
    out[:, :, 2] = lum
    out[:, :, 3] = alpha
    return Image.fromarray(out, mode="RGBA")


def flip_vertical(image: Image.Image) -> Image.Image:
    return image.transpose(Image.FLIP_TOP_BOTTOM)

