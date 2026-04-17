from __future__ import annotations

import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image


def create_step1x3d_router(*, output_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/step1x3d", tags=["step1x3d"])

    @router.get("/models")
    def list_models() -> Dict[str, List[Dict[str, Any]]]:
        models: List[Dict[str, Any]] = []
        if output_dir.exists():
            for glb in sorted(output_dir.glob("*.glb"), key=lambda p: p.stat().st_mtime, reverse=True):
                models.append(
                    {
                        "model_id": glb.stem,
                        "filename": glb.name,
                        "updated_at": glb.stat().st_mtime,
                    }
                )
        return {"models": models}

    @router.get("/models/{model_id}.glb", name="step1x3d_glb_file")
    def get_model_file(model_id: str) -> FileResponse:
        path = output_dir / f"{model_id}.glb"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="GLB not found")
        return FileResponse(
            str(path),
            media_type="model/gltf-binary",
            filename=path.name,
        )

    @router.post("/generate")
    async def generate(
        request: Request,
        file: UploadFile = File(...),
        guidance_scale: float = Form(7.5),
        num_inference_steps: int = Form(50),
        seed: int = Form(2025),
    ) -> Dict[str, Any]:
        if guidance_scale <= 0:
            raise HTTPException(status_code=400, detail="guidance_scale must be positive")
        if num_inference_steps < 1 or num_inference_steps > 200:
            raise HTTPException(status_code=400, detail="num_inference_steps must be between 1 and 200")

        try:
            contents = await file.read()
            img = Image.open(BytesIO(contents))
            img.load()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image upload: {e}") from e

        model_id = uuid.uuid4().hex[:16]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{model_id}.glb"
        lock = request.app.state.step1x3d_lock
        service = request.app.state.step1x3d_service

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            suffix = Path(file.filename or "input.png").suffix or ".png"
            input_path = tmp_path / f"input{suffix}"
            img.save(input_path)
            async with lock:
                try:
                    result = await run_in_threadpool(
                        service.generate_geometry_glb,
                        image_path=input_path,
                        output_path=output_path,
                        guidance_scale=guidance_scale,
                        num_inference_steps=num_inference_steps,
                        seed=seed,
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Step1X-3D generation failed: {e}") from e

        model_url = request.url_for("step1x3d_glb_file", model_id=model_id)
        return {
            "model_id": model_id,
            "filename": output_path.name,
            "model_url": str(model_url),
            "guidance_scale": result["guidance_scale"],
            "num_inference_steps": result["num_inference_steps"],
            "seed": result["seed"],
        }

    @router.delete("/models/{model_id}")
    async def delete_model(model_id: str) -> Dict[str, Any]:
        path = output_dir / f"{model_id}.glb"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="GLB not found")
        path.unlink()
        return {"deleted": model_id}

    return router
