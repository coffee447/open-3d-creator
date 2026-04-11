from enum import Enum
from pydantic import BaseModel


class Direct3ds2Params(BaseModel):
    image: str
    use_alpha: bool = False
    resolution: str = '512'
    simplify: bool = True
    reduce_ratio: float = 0.95
    output_dir: str


class Direct3ds2Response(BaseModel):
    mesh: str