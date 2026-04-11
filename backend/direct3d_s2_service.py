from __future__ import annotations

import datetime
import uuid
from pathlib import Path
from typing import Any, Optional

from PIL import Image
import torch

from models.d3d.pipeline import Direct3DS2Pipeline
from models.d3d.rembg import BiRefNet
from models.d3d.dtypes import Mode

class Direct3DS2Service:
    """
    Loads Direct3D-S2 once and runs image->mesh generation on demand.
    """

    def __init__(
        self,
        *,
        device: str = "cuda:0",
        pipeline_pretrained_path: Optional[Path] = None,
        subfolder: str = "direct3d-s2-v-1-1",
        sdf_resolution: int = 1024,
    ):
        project_root = Path(__file__).resolve().parents[1]
        pipeline_pretrained_path = pipeline_pretrained_path or (
            project_root / "weights/wushuang98/Direct3D-S2"
        )
        pipeline_pretrained_path = pipeline_pretrained_path.resolve()

        self.device = device
        self.rembg = BiRefNet(device=device)
        self.pipe = Direct3DS2Pipeline.from_pretrained(
            str(pipeline_pretrained_path),
            sdf_resolution=sdf_resolution,
            subfolder=subfolder
        )
        self.pipe.to(device, Mode.initial, Mode.dense)

    def generate_img2obj(
        self,
        *,
        image: Image.Image,
        use_alpha: bool,
        resolution: str,
        simplify: bool,
        reduce_ratio: float,
        output_dir: Path,
        mc_threshold: float = 0.2,
        remove_interior: bool = True,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)

        mesh_id = uuid.uuid4().hex
        mesh_path = output_dir / f"{mesh_id}.obj"

        torch.cuda.empty_cache()

        # 1) (optional) segmentation/background processing
        processed_image = self.rembg.run(image, use_alpha=use_alpha)

        # 2) Direct3D-S2 inference
        out = self.pipe(
            processed_image,
            sdf_resolution=int(resolution),
            remesh=bool(simplify),
            simplify_ratio=float(reduce_ratio),
            mc_threshold=float(mc_threshold),
            remove_interior=bool(remove_interior),
        )
        mesh = out.mesh

        # 3) Export mesh to OBJ
        exported = False
        if hasattr(mesh, "export"):
            try:
                mesh.export(str(mesh_path), include_normals=True)
                exported = True
            except TypeError:
                mesh.export(str(mesh_path))
                exported = True

        if not exported:
            # Fallback: rebuild a trimesh from vertices/faces.
            import trimesh

            trimesh.Trimesh(mesh.vertices, mesh.faces).export(str(mesh_path))

        torch.cuda.empty_cache()
        return mesh_path


async def ensure_d3d_service(state: Any, sdf_resolution: int = 1024) -> Direct3DS2Service:
    """
    Create Direct3DS2Service on first use so model weights are not loaded to GPU at app startup.
    Only modules required for the given SDF resolution are moved to VRAM (sparse-1024 stack
    is skipped for 256/512).
    """
    lock = getattr(state, "d3d_service_init_lock", None)
    if lock is None:
        raise RuntimeError("d3d_service_init_lock is not configured on app.state")

    existing = getattr(state, "service", None)
    if existing is not None:
        if int(sdf_resolution) == 1024 and not existing._pipe_has_1024_on_gpu:
            async with lock:
                svc = state.service
                if svc is not None:
                    svc.ensure_gpu_for_resolution(sdf_resolution)
        return state.service

    async with lock:
        if state.service is None:
            state.service = Direct3DS2Service(
                device=state.d3d_device,
                pipeline_pretrained_path=state.d3d_pipeline_pretrained_path,
                subfolder=state.d3d_subfolder,
                sdf_resolution=sdf_resolution,
            )
        else:
            state.service.ensure_gpu_for_resolution(sdf_resolution)
        return state.service

