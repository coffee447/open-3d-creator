"""
Python port of the PIXEstL Java project (models/PIXEstL).

This package focuses on replicating the CLI and ZIP outputs:
- image-color-preview.png
- image-texture-preview.png
- layer-*.stl parts (+ instructions.txt in ADDITIVE mode)
"""

from .cli import main

__all__ = ["main"]

