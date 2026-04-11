from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .color_util import has_transparent_neighbor
from .gen_instruction import GenInstruction, PixelCreationMethod
from .output_sink import OutputSink
from .palette import Palette
from .stl_ascii import cube, solid_begin, solid_end


def _image_to_argb_int(image: Image.Image) -> np.ndarray:
    rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
    a = rgba[:, :, 3].astype(np.uint32)
    r = rgba[:, :, 0].astype(np.uint32)
    g = rgba[:, :, 1].astype(np.uint32)
    b = rgba[:, :, 2].astype(np.uint32)
    return ((a << 24) | (r << 16) | (g << 8) | b).astype(np.uint32)


def _has_any_transparent_pixel(argb_img: np.ndarray) -> bool:
    return bool(np.any((argb_img & 0xFF000000) == 0))


def _adjust_for_offset_layermax(layer_before: int, layer_height: int, offset: int, layer_max: int) -> tuple[int, int] | None:
    """
    Port of the offset/layerMax clipping logic in CSGThreadColorRow.
    """
    if layer_before >= offset + layer_max:
        return None

    if layer_before < offset:
        if layer_before + layer_height < offset:
            return None
        delta = offset - layer_before
        layer_height -= delta
        layer_before = 0
        if layer_height > layer_max:
            layer_height = layer_max
    else:
        if layer_before <= offset:
            layer_before = 0
        elif layer_before > offset:
            layer_before -= offset
        if layer_height + layer_before > layer_max:
            delta = layer_height + layer_before - layer_max
            layer_height -= delta

    if layer_height <= 0:
        return None
    return (layer_before, layer_height)


@dataclass(slots=True)
class StlMaker:
    color_image: Image.Image | None
    texture_image: Image.Image | None
    palette: Palette
    gi: GenInstruction

    FLEXIBLE_COLOR_PLATE_NB: int = 3

    def process(self, sink: OutputSink) -> None:
        # Plate
        if self.color_image is not None:
            self._write_plate(sink)
            self._write_color_layers(sink)

            if self.gi.color_layer and self.gi.pixel_creation_method == PixelCreationMethod.ADDITIVE:
                instructions = self.palette.generate_swap_filaments_instruction()
                print(instructions, end="")
                sink.write_bytes("instructions.txt", instructions.encode("utf-8"))

        # Texture
        if self.texture_image is not None:
            self._write_texture_layer(sink)

    def _write_plate(self, sink: OutputSink) -> None:
        gi = self.gi
        argb = _image_to_argb_int(self.color_image)
        h, w = argb.shape
        px = gi.color_pixel_width
        plate_th = gi.plate_thickness

        transparent_mode = _has_any_transparent_pixel(argb)

        with sink.open_bin("layer-plate.stl") as f:
            solid_begin(f, "layer-plate")

            if not transparent_mode:
                width = w * px
                height = h * px
                cx = (width - px) / 2.0
                cy = (height - px) / 2.0
                cz = (plate_th / 2.0) - plate_th  # -plate_th/2
                cube(f, cx=cx, cy=cy, cz=cz, sx=width, sy=height, sz=plate_th)
            else:
                # Support-only plate under opaque pixels, skipping boundary-adjacent pixels
                for y in range(h):
                    x = 0
                    while x < w:
                        if (argb[y, x] & 0xFF000000) == 0:
                            x += 1
                            continue
                        if has_transparent_neighbor(argb, x, y):
                            x += 1
                            continue

                        # run length of non-transparent, non-boundary pixels
                        k = 0
                        while x + k < w:
                            if (argb[y, x + k] & 0xFF000000) == 0:
                                break
                            if has_transparent_neighbor(argb, x + k, y):
                                break
                            k += 1
                        k -= 1
                        if k < 0:
                            x += 1
                            continue

                        sx = px + px * k
                        cx = x * px + (px * k) / 2.0
                        cy = y * px
                        cz = (plate_th / 2.0) - plate_th
                        cube(f, cx=cx, cy=cy, cz=cz, sx=sx, sy=px, sz=plate_th)
                        x += k + 1

            solid_end(f, "layer-plate")

    def _write_color_layers(self, sink: OutputSink) -> None:
        gi = self.gi
        argb = _image_to_argb_int(self.color_image)
        h, w = argb.shape
        px = gi.color_pixel_width

        transparent_mode = _has_any_transparent_pixel(argb)
        if transparent_mode and gi.curve != 0.0:
            raise ValueError("Curve mode not compatible with image with transparency")

        nb_color_plate = 1
        color_plate_layer_nb = -1
        if gi.curve != 0.0:
            color_plate_layer_nb = self.FLEXIBLE_COLOR_PLATE_NB
            nb_color_plate = gi.color_pixel_layer_number // self.FLEXIBLE_COLOR_PLATE_NB
            nb_color_plate += 1 if (gi.color_pixel_layer_number % self.FLEXIBLE_COLOR_PLATE_NB != 0) else 0

        # Precompute rgb for each pixel (for fast dict lookup)
        r = (argb >> 16) & 0xFF
        g = (argb >> 8) & 0xFF
        b = argb & 0xFF
        rgb_img = np.stack([r, g, b], axis=-1).astype(np.uint8)

        for hex_code_list in self.palette.hex_color_group_list:
            name_parts = [self.palette.get_color_name(hx) for hx in hex_code_list]
            combined_name = "+".join(name_parts)

            for part_idx in range(nb_color_plate):
                prefix = "" if nb_color_plate == 1 else f"{part_idx+1}-"
                thread_name = f"layer-{prefix}{combined_name}"
                fn = f"{thread_name}.stl"

                wrote_any = False
                with sink.open_bin(fn) as f:
                    solid_begin(f, thread_name)

                    for y in range(h):
                        x = 0
                        while x < w:
                            if (argb[y, x] & 0xFF000000) == 0:
                                x += 1
                                continue
                            if transparent_mode and has_transparent_neighbor(argb, x, y):
                                x += 1
                                continue

                            pixel = int(argb[y, x])

                            # run length of identical pixels (and stable boundary in transparency mode)
                            k = 1
                            while x + k < w:
                                if int(argb[y, x + k]) != pixel:
                                    break
                                if transparent_mode and has_transparent_neighbor(argb, x + k, y):
                                    break
                                k += 1
                            k -= 1

                            prgb = (int(rgb_img[y, x, 0]), int(rgb_img[y, x, 1]), int(rgb_img[y, x, 2]))
                            cc = self.palette.quantized_colors.get(prgb)
                            if cc is not None:
                                for hex_code in hex_code_list:
                                    layer_list = cc.get_layer_list(hex_code)
                                    for layer in layer_list:
                                        layer_height = int(layer.layer)
                                        if layer_height == 0:
                                            continue

                                        one_h = gi.color_pixel_layer_thickness
                                        layer_before = cc.layer_position(layer)

                                        if gi.curve != 0.0:
                                            # clip to part range (offset/layerMax)
                                            offset = part_idx * color_plate_layer_nb
                                            layer_max = color_plate_layer_nb
                                            adjusted = _adjust_for_offset_layermax(layer_before, layer_height, offset, layer_max)
                                            if adjusted is None:
                                                continue
                                            layer_before, layer_height = adjusted

                                        cur_h = one_h * layer_height
                                        z_center = (cur_h / 2.0) + layer_before * one_h

                                        sx = px + k * px
                                        sy = px
                                        cx = x * px + (px * k) / 2.0
                                        cy = y * px
                                        cube(f, cx=cx, cy=cy, cz=z_center, sx=sx, sy=sy, sz=cur_h)
                                        wrote_any = True

                            x += k + 1

                    solid_end(f, thread_name)

                if not wrote_any:
                    pass

    def _write_texture_layer(self, sink: OutputSink) -> None:
        gi = self.gi
        tex = self.texture_image.convert("RGBA")
        arr = np.array(tex, dtype=np.uint8)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3]
        h, w = alpha.shape

        tp = gi.texture_pixel_width
        dz = gi.color_pixel_layer_thickness * self.palette.layer_count if gi.color_layer else 0.0

        dx = 0.0
        dy = 0.0
        if gi.color_layer and self.color_image is not None:
            c_w = self.color_image.width * gi.color_pixel_width
            c_h = self.color_image.height * gi.color_pixel_width
            t_w = w * tp
            t_h = h * tp
            diff_w = t_w - c_w
            diff_h = t_h - c_h
            dx = -diff_w / 2.0 - (gi.color_pixel_width - tp) / 2.0
            dy = -diff_h / 2.0 - (gi.color_pixel_width - tp) / 2.0

        # Find white filament name for filename, like Java picks the brightest hex in getColorHexList().
        # Java sorts getColorHexList() and picks last; we approximate by picking #FFFFFF if present.
        white_hex = "#FFFFFF" if "#FFFFFF" in self.palette.get_color_hex_list() else None
        if white_hex is None:
            # fallback: brightest by RGB energy
            from .color_util import hex_to_rgb, rgb_energy

            all_hex = self.palette.get_color_hex_list()
            all_hex.sort(key=lambda hx: rgb_energy(hex_to_rgb(hx)))
            white_hex = all_hex[-1]
        white_name = self.palette.get_color_name(white_hex)

        thread_name = f"layer-texture-{white_name}"
        fn = f"{thread_name}.stl"

        with sink.open_bin(fn) as f:
            solid_begin(f, thread_name)
            for y in range(h):
                for x in range(w):
                    if alpha[y, x] == 0:
                        continue
                    lum = int(rgb[y, x, 0])  # already grayscale in input
                    k = 1.0 - (lum / 255.0)
                    height = k * (gi.texture_max_thickness - gi.texture_min_thickness) + gi.texture_min_thickness
                    cx = x * tp + dx
                    cy = y * tp + dy
                    cz = dz + height / 2.0
                    cube(f, cx=cx, cy=cy, cz=cz, sx=tp, sy=tp, sz=height)
            solid_end(f, thread_name)

