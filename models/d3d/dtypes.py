from enum import Enum
from pydantic import BaseModel
from trimesh import Trimesh
from typing_extensions import Any
from enum import Enum
from pydantic import BaseModel
from pathlib import Path
import torch


class ImageMode(Enum):
    rgba = 'RGBA'


class Mode(Enum):
    initial = 'initial'
    dense = 'dense'
    sparse512 = 'sparse512'
    sparse1024 = 'sparse1024'


class Device(Enum):
    cpu = 'cpu'
    gpu = 'cuda'


class Backends(Enum):
    xformers = 'xformers'
    flash_attn = 'flash_attn'
    sdpa = 'sdpa'
    naive = 'naive'


class SparseBackends(Enum):
    torchsparse = 'torchsparse'
    spconv = 'spconv'


class SpconvAlgo(Enum):
    native = 'native'
    implicit_gemm = 'implicit_gemm'
    auto = 'auto'


class Output(BaseModel):
    mesh: object


class DenseDecoderInputs(BaseModel):
    latents: object
    voxel_resolution: int = 64
    mc_threshold: float = 0.5
    return_index: bool = False


class DiffusionInputs(BaseModel):
    x: object
    t: object
    cond: object


class SparseDecoderInputs(BaseModel):
    latents: object
    voxel_resolution: int = 512
    mc_threshold: float = 0.2
    return_feat: bool = False
    factor: float = 1.0


class Urls(Enum):
    local: str = 'http://127.0.0.1:8888'


class Endpoints(Enum):
    img2obj: str = 'direct3d-s2/img2obj'


class Samplers(Enum):
    dpmpp2m: str = "DPM++ 2M"


class Direct3ds2Params(BaseModel):
    image: str
    use_alpha: bool = False
    resolution: str = '512'
    simplify: bool = True
    reduce_ratio: float = 0.95
    output_dir: str


class Direct3ds2Response(BaseModel):
    mesh: str