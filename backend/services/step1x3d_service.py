from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict


class Step1X3DService:
    def __init__(self, *, project_root: Path, device: str = "cuda") -> None:
        self.project_root = project_root
        self.device = device
        self.repo_dir = project_root / "models" / "Step1X-3D"
        self._geometry_pipeline = None

    def _ensure_import_path(self) -> None:
        repo_str = str(self.repo_dir)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

    def _ensure_geometry_pipeline(self) -> Any:
        if self._geometry_pipeline is not None:
            return self._geometry_pipeline
        self._ensure_import_path()
        from step1x3d_geometry.models.pipelines.pipeline import Step1X3DGeometryPipeline  # type: ignore

        self._geometry_pipeline = Step1X3DGeometryPipeline.from_pretrained(
            "stepfun-ai/Step1X-3D",
            subfolder="Step1X-3D-Geometry-1300m",
        ).to(self.device)
        return self._geometry_pipeline

    def generate_geometry_glb(
        self,
        *,
        image_path: Path,
        output_path: Path,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50,
        seed: int = 2025,
    ) -> Dict[str, Any]:
        import torch  # lazy import for startup speed and optional envs

        pipe = self._ensure_geometry_pipeline()
        generator = torch.Generator(device=pipe.device).manual_seed(seed)
        out = pipe(
            str(image_path),
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            generator=generator,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out.mesh[0].export(output_path)
        return {
            "output_path": str(output_path),
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "seed": seed,
        }
