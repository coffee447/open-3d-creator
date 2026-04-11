from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
from PIL import Image

from .color_util import (
    cmyk_to_rgb,
    color_to_cmyk,
    hex_to_rgb,
    hexcode_energy,
    k_of_hex,
    rgb_to_lab_array,
)
from .gen_instruction import GenInstruction, PixelCreationMethod


@dataclass(frozen=True, slots=True)
class ColorLayer:
    hex_code: str
    layer: int
    c: float
    m: float
    y: float
    k: float


@dataclass(slots=True)
class ColorCombi:
    layers: list[ColorLayer]

    @classmethod
    def from_layer(cls, layer: ColorLayer) -> "ColorCombi":
        return cls(layers=[layer])

    def duplicate(self) -> "ColorCombi":
        return ColorCombi(layers=list(self.layers))

    def total_layers(self) -> int:
        return int(sum(l.layer for l in self.layers))

    def total_colors(self) -> int:
        return len(self.layers)

    def combine_litho_color_layer(self, layer2: ColorLayer, nb_layer_max: int) -> "ColorCombi | None":
        if any(l.hex_code == layer2.hex_code for l in self.layers):
            return None
        if self.total_layers() + layer2.layer > nb_layer_max:
            return None
        c = self.duplicate()
        c.layers.append(layer2)
        return c

    def combine_litho_color_combi(self, other: "ColorCombi") -> "ColorCombi":
        c = self.duplicate()
        c.layers.extend(other.layers)
        return c

    def factorize(self) -> None:
        # Merge consecutive identical hex codes (Java's factorize assumes layers already in desired order)
        if not self.layers:
            return
        new_layers: list[ColorLayer] = []
        for cur in self.layers:
            if not new_layers:
                new_layers.append(cur)
                continue
            last = new_layers[-1]
            if last.hex_code == cur.hex_code:
                new_layers[-1] = ColorLayer(
                    hex_code=last.hex_code,
                    layer=last.layer + cur.layer,
                    c=last.c,
                    m=last.m,
                    y=last.y,
                    k=last.k,
                )
            else:
                new_layers.append(cur)
        self.layers = new_layers

    def get_color_rgb(self, gi: GenInstruction) -> tuple[int, int, int]:
        c = m = y = k = 0.0
        for l in self.layers:
            if gi.debug:
                print(f"{l.hex_code}[{l.layer}]", end="")
            c += l.c
            m += l.m
            y += l.y
            k += l.k
        rgb = cmyk_to_rgb(min(c, 1.0), min(m, 1.0), min(y, 1.0), min(k, 1.0))
        if gi.debug:
            print(f"={rgb}")
        return rgb

    def get_layer_list(self, hex_code: str) -> list[ColorLayer]:
        return [l for l in self.layers if l.hex_code == hex_code]

    def layer_position(self, layer: ColorLayer) -> int:
        before = 0
        for cur in self.layers:
            if cur is layer:
                break
            before += cur.layer
        return before


class Palette:
    """
    Port of ggo.pixestl.palette.Palette.
    """

    def __init__(self, path: str, gi: GenInstruction):
        self.gi = gi
        self.nb_layers = 0

        # Java keeps name mapping even for inactive colors.
        self.name_by_hex: dict[str, str] = {}

        # Active colors list used for grouping; includes #FFFFFF only when active & valid.
        self.hex_color_list: list[str] = []
        self.hex_color_group_list: list[list[str]] = []

        self.nb_group = 0
        self.layer_count = 0

        # Mapping from composite RGB -> combi
        self.quantized_colors: dict[tuple[int, int, int], ColorCombi] = {}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        color_layer_list: list[ColorLayer] = []

        for hex_color, obj in data.items():
            color_name = obj["name"]
            self.name_by_hex[hex_color] = color_name

            active = obj.get("active", True)
            if not active:
                continue

            if "layers" in obj and gi.pixel_creation_method == PixelCreationMethod.ADDITIVE:
                layers_obj = obj["layers"]
                nb_l = 0
                # Note: Java increments nbL per key iteration (unordered); we just track max via parsed int.
                for layer_key, layer_def in layers_obj.items():
                    nb_l += 1
                    self.nb_layers = max(self.nb_layers, nb_l)
                    layer_n = int(layer_key)
                    if "hexcode" in layer_def:
                        rgb = hex_to_rgb(layer_def["hexcode"])
                        # Java: hex->Color->HSL then HSL->CMYK
                        # We can derive CMYK via HSL path only if needed, but palette files provide HSL already.
                        # To match Java, interpret "hexcode" as the measured layer color (RGB) -> CMYK.
                        c, m, y, k = color_to_cmyk(rgb)
                    else:
                        h = float(layer_def["H"])
                        s = float(layer_def["S"])
                        l = float(layer_def["L"])
                        # Java uses hslToCmyk; here we reconstruct by converting HSL->RGB via same algorithm
                        # is unnecessary; we compute CMYK via the Java-equivalent HSL->CMYK in color_util.
                        from .color_util import hsl_to_cmyk

                        c, m, y, k = hsl_to_cmyk(h, s, l)

                    color_layer_list.append(ColorLayer(hex_code=hex_color, layer=layer_n, c=c, m=m, y=y, k=k))

                if hex_color not in self.hex_color_list:
                    self.hex_color_list.append(hex_color)

            elif gi.pixel_creation_method == PixelCreationMethod.FULL:
                rgb = hex_to_rgb(hex_color)
                # FULL mode: treat filament as a full-thickness single layer in CMYK space
                from .color_util import color_to_hsl, hsl_to_cmyk

                h, s, l = color_to_hsl(rgb)
                c, m, y, k = hsl_to_cmyk(h, s, l)
                color_layer_list.append(
                    ColorLayer(hex_code=hex_color, layer=gi.color_pixel_layer_number, c=c, m=m, y=y, k=k)
                )
                if hex_color not in self.hex_color_list:
                    self.hex_color_list.append(hex_color)

        if gi.pixel_creation_method == PixelCreationMethod.ADDITIVE and "#FFFFFF" not in self.hex_color_list:
            raise ValueError('"#FFFFFF" not found in the palette. The code "#FFFFFF" is mandatory in additive mode.')

        self.nb_layers = gi.color_pixel_layer_number

        # Sort like Java
        color_layer_list.sort(key=lambda cl: k_of_hex(cl.hex_code), reverse=True)
        self.hex_color_list.sort(key=hexcode_energy)

        self._compute_colors_by_group(color_layer_list)

    def get_color_hex_list(self) -> list[str]:
        return list(self.name_by_hex.keys())

    def get_color_name(self, hex_code: str) -> str:
        return self.name_by_hex[hex_code]

    def get_colors_rgb(self) -> list[tuple[int, int, int]]:
        return list(self.quantized_colors.keys())

    def get_color_combi(self, rgb: tuple[int, int, int]) -> ColorCombi:
        return self.quantized_colors[rgb]

    def _create_multi_combi(
        self, restrict_hex_list: list[str] | None, color_layer_list: list[ColorLayer]
    ) -> list[ColorCombi]:
        combis: list[ColorCombi] = []
        for i, layer in enumerate(color_layer_list):
            if restrict_hex_list is not None and layer.hex_code not in restrict_hex_list:
                continue
            c0 = ColorCombi.from_layer(layer)
            combis.append(c0)
            if i + 1 < len(color_layer_list):
                combis.extend(self._compute_combination(restrict_hex_list, c0, color_layer_list))

        final: list[ColorCombi] = [c for c in combis if c.total_layers() == self.gi.color_pixel_layer_number]
        return final

    def _compute_combination(
        self, restrict_hex_list: list[str] | None, combi: ColorCombi, color_layer_list: list[ColorLayer]
    ) -> list[ColorCombi]:
        res: list[ColorCombi] = []
        for i, layer in enumerate(color_layer_list):
            if restrict_hex_list is not None and layer.hex_code not in restrict_hex_list:
                continue
            if combi.total_layers() + layer.layer > self.nb_layers:
                continue
            if combi.total_colors() >= len(self.name_by_hex):
                break
            combi2 = combi.combine_litho_color_layer(layer, self.nb_layers)
            if combi2 is None:
                continue
            if combi2.total_layers() == self.gi.color_pixel_layer_number:
                res.append(combi2)
            if i + 1 < len(color_layer_list):
                res.extend(self._compute_combination(restrict_hex_list, combi2, color_layer_list))
        return res

    def _optimize_white_layer(self, nb_color_pool: int) -> None:
        # Reorder layers in each combi: white layers to bottom/top, colored in middle.
        for rgb, cc in list(self.quantized_colors.items()):
            bottom: list[ColorLayer] = []
            middle: list[ColorLayer] = []
            top: list[ColorLayer] = []
            lsum = 0
            for cl in cc.layers:
                if cl.hex_code == "#FFFFFF":
                    if lsum <= nb_color_pool:
                        bottom.append(cl)
                    else:
                        top.append(cl)
                else:
                    middle.append(cl)
                lsum += cl.layer
            cc.layers = bottom + middle + top

    def _init_hex_color_group_list(self, hex_color_groups: list[list[str]], nb_color_pool: int) -> None:
        self.hex_color_group_list = [[] for _ in range(nb_color_pool)]

        for group_layer in hex_color_groups:
            if "#FFFFFF" in group_layer:
                group_layer = [h for h in group_layer if h != "#FFFFFF"]
            for i in range(nb_color_pool):
                if i >= len(group_layer):
                    continue
                self.hex_color_group_list[i].append(group_layer[i])

        self.hex_color_group_list.append(["#FFFFFF"])

    def _compute_colors_by_group(self, color_layer_list: list[ColorLayer]) -> None:
        # Mirrors Java's computeColorsByGroup
        if "#FFFFFF" in self.hex_color_list:
            self.hex_color_list.remove("#FFFFFF")

        nb_color_pool = len(self.hex_color_list)
        if self.gi.pixel_creation_method == PixelCreationMethod.ADDITIVE and self.gi.color_number != 0:
            nb_color_pool = self.gi.color_number - 1
            nb_color_pool = max(1, nb_color_pool)

        self.nb_group = len(self.hex_color_list) // nb_color_pool
        self.nb_group += 0 if (len(self.hex_color_list) % nb_color_pool == 0) else 1

        hex_color_groups: list[list[str]] = [[] for _ in range(self.nb_group)]
        for i in range(self.nb_group):
            for j in range(nb_color_pool):
                idx = nb_color_pool * i + j
                if idx >= len(self.hex_color_list):
                    break
                hex_color_groups[i].append(self.hex_color_list[idx])

        combis_by_group: list[list[ColorCombi]] = []
        for i in range(self.nb_group):
            group = list(hex_color_groups[i])
            group.append("#FFFFFF")
            combis_by_group.append(self._create_multi_combi(group, color_layer_list))

        # Cartesian product / progressive combine
        temp_lists: list[list[ColorCombi]] = [combis_by_group[0]]
        for i in range(self.nb_group - 1):
            combined: list[ColorCombi] = []
            for c0 in temp_lists[i]:
                for c1 in combis_by_group[i + 1]:
                    combined.append(c0.combine_litho_color_combi(c1))
            temp_lists.append(combined)

        final_combis = temp_lists[-1]

        self.layer_count = self.nb_layers * self.nb_group

        self.quantized_colors = {}
        for c in final_combis:
            c.factorize()
            rgb = c.get_color_rgb(self.gi)
            self.quantized_colors[rgb] = c

        self._optimize_white_layer(nb_color_pool)
        self._init_hex_color_group_list(hex_color_groups, nb_color_pool)

    def restrict_full_colors(self, image: Image.Image, color_number: int) -> None:
        # Port of Palette.restrictFullColors (used to pick frequent filaments)
        pixelated = image
        quant = self.quantize_colors(pixelated)

        arr = np.array(quant.convert("RGBA"), dtype=np.uint8)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3]

        color_counts: dict[str, int] = {}

        for y in range(arr.shape[0]):
            for x in range(arr.shape[1]):
                if alpha[y, x] == 0:
                    continue
                px = tuple(int(v) for v in rgb[y, x])
                cc = self.quantized_colors.get(px)
                if cc is None:
                    continue
                for cl in cc.layers:
                    count = color_counts.get(cl.hex_code, 0)
                    nb_layer = cl.layer
                    # Java special-case for black 5 layers
                    if cl.hex_code == "#000000" and nb_layer == 5:
                        nb_layer = 1
                    color_counts[cl.hex_code] = count + nb_layer

        sorted_colors = sorted(color_counts.items(), key=lambda kv: kv[1], reverse=True)

        most_freq: list[str] = []
        for hex_code, _ in sorted_colors:
            if hex_code == "#FFFFFF":
                most_freq.append("#FFFFFF")
                color_number -= 1
        for hex_code, _ in sorted_colors[: max(0, min(len(sorted_colors), color_number))]:
            if hex_code not in most_freq:
                most_freq.append(hex_code)

        new_quantized: dict[tuple[int, int, int], ColorCombi] = {}
        for rgb_key, cc in self.quantized_colors.items():
            excluded = any(cl.hex_code not in most_freq for cl in cc.layers)
            if not excluded:
                new_quantized[rgb_key] = cc
        self.quantized_colors = new_quantized

        # Keep only used hex codes in name map (like Java)
        new_name_map: dict[str, str] = {}
        used_hex: set[str] = set()
        for cc in self.quantized_colors.values():
            for cl in cc.layers:
                used_hex.add(cl.hex_code)
        for hex_code, name in self.name_by_hex.items():
            if hex_code in used_hex:
                new_name_map[hex_code] = name
        self.name_by_hex = new_name_map

    def quantize_colors(self, image: Image.Image) -> Image.Image:
        """
        Map each pixel to closest available composite palette color.
        """
        rgba = image.convert("RGBA")
        arr = np.array(rgba, dtype=np.uint8)
        rgb = arr[:, :, :3]
        alpha = arr[:, :, 3]

        palette_rgbs = np.array(self.get_colors_rgb(), dtype=np.uint8)
        if palette_rgbs.size == 0:
            raise ValueError("Palette has no colors to quantize with.")

        # Vectorized nearest neighbor using ||p-c||^2 = p^2 + c^2 - 2 p·c
        if self.gi.color_distance_computation.name == "RGB":
            c = palette_rgbs.astype(np.int32)
        else:
            c = rgb_to_lab_array(palette_rgbs)

        out_rgb = np.zeros_like(rgb)

        # Process row blocks to keep memory bounded
        for y in range(rgb.shape[0]):
            mask = alpha[y] != 0
            if not np.any(mask):
                continue
            row = rgb[y, mask]
            if self.gi.color_distance_computation.name == "RGB":
                p = row.astype(np.int32)
            else:
                p = rgb_to_lab_array(row)

            p_, c_ = np.expand_dims(p, 1), np.expand_dims(c, 0)
            dist = np.sum(-2 * p_ * c_ + (p_ * p_) + (c_ * c_), axis=2)
            idx = np.argmin(dist, axis=1)
            out_rgb[y, mask] = palette_rgbs[idx]

        out = np.zeros_like(arr)
        out[:, :, :3] = out_rgb
        out[:, :, 3] = alpha

        # Shrink quantized color set to actually used colors (Java behavior)
        used = set()
        used.update(tuple(int(v) for v in row) for row in out_rgb.reshape(-1, 3) if True)
        used = {u for u in used if u != (0, 0, 0)}  # keep simple; alpha mask is authoritative
        # Filter based on pixels actually present (alpha != 0)
        used2: set[tuple[int, int, int]] = set()
        flat_alpha = alpha.reshape(-1)
        flat_rgb = out_rgb.reshape(-1, 3)
        for i in range(flat_rgb.shape[0]):
            if flat_alpha[i] == 0:
                continue
            used2.add(tuple(int(v) for v in flat_rgb[i]))
        self.quantized_colors = {rgb_key: self.quantized_colors[rgb_key] for rgb_key in used2 if rgb_key in self.quantized_colors}
        print(f"Nb color used={len(self.quantized_colors)}")

        return Image.fromarray(out, mode="RGBA")

    def generate_swap_filaments_instruction(self) -> str:
        layer_idx = 0.0
        sb: list[str] = []
        for i in range(self.nb_group):
            line = [f"Layer[{layer_idx}] :"]
            j = 0
            for hex_group in self.hex_color_group_list:
                if i >= len(hex_group):
                    continue
                if j != 0:
                    line.append(", ")
                j += 1
                if i != 0:
                    line.append(self.get_color_name(hex_group[i - 1]))
                    line.append("-->")
                line.append(self.get_color_name(hex_group[i]))
            sb.append("".join(line))
            if i == 0:
                layer_idx += self.gi.plate_thickness
            layer_idx += self.gi.color_pixel_layer_thickness * (self.gi.color_pixel_layer_number + 1)
        return "\n".join(sb) + "\n"

