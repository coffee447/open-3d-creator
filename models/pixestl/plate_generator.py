from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

from PIL import Image

from .gen_instruction import GenInstruction, PixelCreationMethod
from .image_util import (
    check_ratio,
    convert_to_black_and_white,
    flip_vertical,
    resize_image,
)
from .output_sink import DirSink, ZipSink
from .palette import Palette
from .stl_maker import StlMaker


class PlateGenerator:
    def process(self, gi: GenInstruction) -> None:
        start = time.time()

        print("Palette generation... ", end="")
        palette = Palette(gi.palette_path, gi)
        print(f"({len(palette.get_colors_rgb())} colors found)")

        image = Image.open(gi.src_image_path).convert("RGBA")
        check_ratio(image, gi.dest_image_width, gi.dest_image_height)

        if gi.pixel_creation_method == PixelCreationMethod.FULL and gi.color_number != 0:
            palette.restrict_full_colors(image, gi.color_number)

        quantized_color_image = None
        texture_image = None

        if gi.color_layer:
            color_image = resize_image(image, gi.dest_image_width, gi.dest_image_height, gi.color_pixel_width)
            print("Calculating color distances with the image...")
            quantized_color_image = palette.quantize_colors(color_image)

        if gi.texture_layer:
            tex = resize_image(image, gi.dest_image_width, gi.dest_image_height, gi.texture_pixel_width)
            texture_image = convert_to_black_and_white(tex)

        flip_color = flip_vertical(quantized_color_image) if quantized_color_image is not None else None
        flip_tex = flip_vertical(texture_image) if texture_image is not None else None

        maker = StlMaker(flip_color, flip_tex, palette, gi)

        print("Generating previews...")
        if gi.dest_output_dir:
            root = Path(gi.dest_output_dir)
            root.mkdir(parents=True, exist_ok=True)
            sink = DirSink(root)
            self._write_outputs(sink, quantized_color_image, texture_image, maker)
        else:
            if not gi.dest_zip_path:
                raise ValueError("dest_zip_path or dest_output_dir is required")
            with zipfile.ZipFile(gi.dest_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                sink = ZipSink(zf)
                self._write_outputs(sink, quantized_color_image, texture_image, maker)

        elapsed_ms = int((time.time() - start) * 1000)
        print(f"GENERATION COMPLETE ! ({elapsed_ms} ms)")

    def _write_outputs(self, sink, quantized_color_image, texture_image, maker: StlMaker) -> None:
        if quantized_color_image is not None:
            buf = io.BytesIO()
            quantized_color_image.save(buf, format="PNG")
            sink.write_bytes("image-color-preview.png", buf.getvalue())
        if texture_image is not None:
            buf = io.BytesIO()
            texture_image.save(buf, format="PNG")
            sink.write_bytes("image-texture-preview.png", buf.getvalue())

        print("Generating STL files...")
        maker.process(sink)
