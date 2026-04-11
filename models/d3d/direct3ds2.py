
import torch

import datetime

from models.d3d.pipeline import Direct3DS2Pipeline
from models.d3d.utils import postprocess_mesh

import os
from typing import Any
import PIL

# from gradio import Image
from pathlib import Path


pipe = Direct3DS2Pipeline.from_pretrained('weights/wushuang98/Direct3D-S2', subfolder="direct3d-s2-v-1-1")
pipe.to("cuda:0", sdf_resolution=1024)


def check_input_image(input_image):
    assert Path(input_image).exists()
    return PIL.Image.open(input_image)


# -----------------------------------------------------------------------------
#  PLACEHOLDER BACK-END HOOKS  ▸  replace with your real logic
# -----------------------------------------------------------------------------
def image2mesh(
    image: Any, 
    resolution: str = '1024', 
    simplify: bool = True,
    simplify_ratio: float = 0.95, 
    output_dir: str = 'outputs/web'
):
    
    torch.cuda.empty_cache()
    
    uid = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # image.save(os.path.join(output_dir, uid + '.png'))

    mesh = pipe(
        image, 
        sdf_resolution=int(resolution), 
        mc_threshold=0.2,
        remesh=simplify,
        simplify_ratio=simplify_ratio,
    ).mesh

    mesh_path = os.path.join(output_dir, f'{uid}.obj')
    mesh.export(
        mesh_path,
        include_normals=True,
    )
    torch.cuda.empty_cache()
    return mesh_path
            