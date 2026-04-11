from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from typing import Literal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MODELS = _PROJECT_ROOT / "models"
if str(_MODELS) not in sys.path:
    sys.path.insert(0, str(_MODELS))

from pixestl.gen_instruction import ColorDistanceComputation, GenInstruction, PixelCreationMethod
from pixestl.plate_generator import PlateGenerator

DEFAULT_PALETTE = _PROJECT_ROOT / "repositories/pixestl/filament-palette-0.10mm.json"


def generate_layer_zip(
    *,
    src_image_path: Path,
    palette_path: Path,
    dest_image_width: float,
    dest_zip_path: Path,
    color_distance: Literal["RGB", "CIELab"] = "CIELab",
) -> Path:
    """Run PIXEstL plate generation; writes ZIP at ``dest_zip_path``."""
    if not palette_path.is_file():
        raise FileNotFoundError(f"Palette not found: {palette_path}")
    dest_zip_path.parent.mkdir(parents=True, exist_ok=True)

    gi = GenInstruction(
        src_image_path=str(src_image_path.resolve()),
        palette_path=str(palette_path.resolve()),
        dest_image_width=dest_image_width,
        dest_image_height=0.0,
        dest_zip_path=str(dest_zip_path.resolve()),
        pixel_creation_method=PixelCreationMethod.ADDITIVE,
        color_distance_computation=ColorDistanceComputation(color_distance),
    )
    gi.finalize()
    PlateGenerator().process(gi)
    return dest_zip_path


def generate_layer_preview(
    *,
    src_image_path: Path,
    palette_path: Path,
    dest_image_width: float,
    dest_dir_path: Path,
    color_distance: Literal["RGB", "CIELab"] = "CIELab",
) -> Path:
    """Run PIXEstL plate generation; writes loose files under ``dest_dir_path`` (no ZIP)."""
    if not palette_path.is_file():
        raise FileNotFoundError(f"Palette not found: {palette_path}")
    dest_dir_path.mkdir(parents=True, exist_ok=True)

    gi = GenInstruction(
        src_image_path=str(src_image_path.resolve()),
        palette_path=str(palette_path.resolve()),
        dest_image_width=dest_image_width,
        dest_image_height=0.0,
        dest_zip_path=None,
        dest_output_dir=str(dest_dir_path.resolve()),
        pixel_creation_method=PixelCreationMethod.ADDITIVE,
        color_distance_computation=ColorDistanceComputation(color_distance),
    )
    gi.finalize()
    PlateGenerator().process(gi)
    return dest_dir_path


def pack_session_dir_to_zip(*, session_dir: Path, dest_zip_path: Path) -> Path:
    """Zip all files in ``session_dir`` (flat) into ``dest_zip_path``."""
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")
    dest_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(session_dir.iterdir()):
            if fp.is_file():
                zf.write(fp, fp.name)
    return dest_zip_path
