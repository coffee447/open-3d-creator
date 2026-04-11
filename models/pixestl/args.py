from __future__ import annotations

import argparse

from .gen_instruction import (
    ColorDistanceComputation,
    GenInstruction,
    PixelCreationMethod,
)


def _boolish(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def parse_args(argv: list[str] | None = None) -> GenInstruction:
    p = argparse.ArgumentParser(prog="PIXEstL (python)", add_help=True)

    # Required
    p.add_argument("-i", "--srcImagePath", required=True, dest="src_image_path", help="Path to the source image.")
    p.add_argument("-p", "--palettePath", required=True, dest="palette_path", help="Path to the palette file.")

    # Destination sizing
    p.add_argument("-w", "--destImageWidth", type=float, dest="dest_image_width", default=0.0, help="Width of the destination image (mm).")
    p.add_argument("-H", "--destImageHeight", type=float, dest="dest_image_height", default=0.0, help="Height of the destination image (mm).")

    # Output
    p.add_argument("-o", "--destZipPath", dest="dest_zip_path", default=None, help="Destination ZIP file path. Default: <-image>.zip")

    # Palette / quantization
    p.add_argument("-c", "--colorNumber", type=int, dest="color_number", default=0, help="Maximum number of color number by layer. Default: no limits")
    p.add_argument(
        "-F",
        "--pixelCreationMethod",
        dest="pixel_creation_method",
        default=PixelCreationMethod.ADDITIVE.value,
        choices=[e.value for e in PixelCreationMethod],
        help="Method for pixel creation [ADDITIVE,FULL]. Default: ADDITIVE",
    )
    p.add_argument(
        "-d",
        "--colorDistanceComputation",
        dest="color_distance_computation",
        default=ColorDistanceComputation.CIELab.value,
        choices=[e.value for e in ColorDistanceComputation],
        help="Method for pixel color distance computation [RGB,CIELab]. Default: CIELab",
    )

    # Geometry
    p.add_argument("-f", "--plateThickness", type=float, dest="plate_thickness", default=0.2, help="Thickness of the plate (mm). Default: 0.2")
    p.add_argument("-l", "--colorLayerNumber", type=int, dest="color_pixel_layer_number", default=5, help="Number of color pixel layers. Default: 5")
    p.add_argument("-b", "--colorPixelLayerThickness", type=float, dest="color_pixel_layer_thickness", default=0.1, help="Thickness of each color pixel layer (mm). Default: 0.1")
    p.add_argument("-cW", "--colorPixelWidth", type=float, dest="color_pixel_width", default=0.8, help="Width of color pixels (mm). Default: 0.8")
    p.add_argument("-M", "--textureMaxThickness", type=float, dest="texture_max_thickness", default=1.8, help="Maximum thickness of the texture (mm). Default: 1.8")
    p.add_argument("-m", "--textureMinThickness", type=float, dest="texture_min_thickness", default=0.3, help="Minimum thickness of the texture (mm). Default: 0.3")
    p.add_argument("-tW", "--texturePixelWidth", type=float, dest="texture_pixel_width", default=0.25, help="Width of texture pixels (mm). Default: 0.25")

    # Concurrency / timeouts (accepted for compatibility)
    p.add_argument("-n", "--layerThreadMaxNumber", type=int, dest="layer_thread_max_number", default=0, help="Maximum number of threads for layers generation. Default: 1 by STL layer")
    p.add_argument("-t", "--layerThreadTimeout", type=int, dest="layer_thread_timeout", default=300, help="Timeout for layer threads (second). Default: 300")
    p.add_argument("-N", "--rowThreadMaxNumber", type=int, dest="row_thread_max_number", default=0, help="Number of threads for rows generation. Default: number of cores available")
    p.add_argument("-T", "--rowThreadTimeout", type=int, dest="row_thread_timeout", default=120, help="Timeout for row threads (second). Default: 120")

    p.add_argument("-Y", "--lowMemory", action="store_true", dest="low_memory", help="Low Memory mode (ignored in python port; always streamed).")
    p.add_argument("-X", "--debug", action="store_true", dest="debug", help="Debug mode")
    p.add_argument("-C", "--curve", type=float, dest="curve", default=0.0, help="Curve parameter. Default: no curve")

    p.add_argument("-z", "--colorLayer", type=_boolish, dest="color_layer", default=True, help="Color layers will generate or not. Default: true")
    p.add_argument("-Z", "--textureLayer", type=_boolish, dest="texture_layer", default=True, help="Texture layers will generate or not. Default: true")

    ns = p.parse_args(argv)

    gi = GenInstruction(
        src_image_path=ns.src_image_path,
        palette_path=ns.palette_path,
        dest_image_width=ns.dest_image_width,
        dest_image_height=ns.dest_image_height,
        dest_zip_path=ns.dest_zip_path,
        color_number=ns.color_number,
        pixel_creation_method=PixelCreationMethod(ns.pixel_creation_method),
        color_distance_computation=ColorDistanceComputation(ns.color_distance_computation),
        plate_thickness=ns.plate_thickness,
        color_pixel_width=ns.color_pixel_width,
        color_pixel_layer_thickness=ns.color_pixel_layer_thickness,
        color_pixel_layer_number=ns.color_pixel_layer_number,
        texture_pixel_width=ns.texture_pixel_width,
        texture_min_thickness=ns.texture_min_thickness,
        texture_max_thickness=ns.texture_max_thickness,
        layer_thread_max_number=ns.layer_thread_max_number,
        row_thread_max_number=ns.row_thread_max_number,
        layer_thread_timeout=ns.layer_thread_timeout,
        row_thread_timeout=ns.row_thread_timeout,
        curve=ns.curve,
        color_layer=ns.color_layer,
        texture_layer=ns.texture_layer,
        debug=ns.debug,
        low_memory=ns.low_memory,
    )

    return gi.finalize()

