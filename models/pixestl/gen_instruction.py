from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PixelCreationMethod(str, Enum):
    ADDITIVE = "ADDITIVE"
    FULL = "FULL"


class ColorDistanceComputation(str, Enum):
    RGB = "RGB"
    CIELab = "CIELab"


@dataclass(slots=True)
class GenInstruction:
    # Required
    src_image_path: str
    palette_path: str

    # Destination sizing (mm)
    dest_image_width: float = 0.0
    dest_image_height: float = 0.0

    # Output (exactly one of ``dest_zip_path`` or ``dest_output_dir`` after ``finalize()``)
    dest_zip_path: str | None = None
    """Write outputs into a single ZIP file (CLI default)."""

    dest_output_dir: str | None = None
    """Write loose files into this directory (no ZIP). Used for preview-then-export flows."""

    # Palette / quantization
    color_number: int = 0  # 0 => no limit
    pixel_creation_method: PixelCreationMethod = PixelCreationMethod.ADDITIVE
    color_distance_computation: ColorDistanceComputation = ColorDistanceComputation.CIELab

    # Geometry parameters (mm)
    plate_thickness: float = 0.2
    color_pixel_width: float = 0.8
    color_pixel_layer_thickness: float = 0.1
    color_pixel_layer_number: int = 5
    texture_pixel_width: float = 0.25
    texture_min_thickness: float = 0.3
    texture_max_thickness: float = 1.8

    # Concurrency (kept for CLI compatibility; Python port is single-process for now)
    layer_thread_max_number: int = 0
    row_thread_max_number: int = 0
    layer_thread_timeout: int = 300
    row_thread_timeout: int = 120

    # Other
    curve: float = 0.0
    color_layer: bool = True
    texture_layer: bool = True
    debug: bool = False
    low_memory: bool = False

    def finalize(self) -> "GenInstruction":
        if self.dest_image_width == 0.0 and self.dest_image_height == 0.0:
            raise ValueError("A width or a height is mandatory (use -w and/or -H).")
        if self.dest_output_dir:
            return self
        if not self.dest_zip_path:
            out_name = self.src_image_path
            dot = out_name.rfind(".")
            if dot > 0:
                out_name = out_name[:dot]
            self.dest_zip_path = f"{out_name}.zip"
        return self

