from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image

from ..d3d_ops import list_mesh_entries, resolve_mesh_path
from ..direct3d_s2_service import Direct3DS2Service, ensure_d3d_service


def create_d3d_router(*, mesh_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/d3d", tags=["d3d"])

    @router.get("/meshes")
    def list_meshes() -> Dict[str, List[Dict[str, Any]]]:
        return {"meshes": list_mesh_entries(mesh_dir)}

    @router.get("/meshes/{mesh_id}.obj", name="d3d_mesh_obj")
    def get_mesh_obj(mesh_id: str, request: Request) -> FileResponse:
        mesh_path = resolve_mesh_path(mesh_dir, mesh_id)
        if mesh_path is None:
            raise HTTPException(status_code=404, detail="Mesh not found")
        return FileResponse(
            str(mesh_path),
            media_type="model/obj",
            filename=mesh_path.name,
        )

    @router.post("/mesh/img2obj")
    async def img2obj_upload(
        request: Request,
        file: UploadFile = File(...),
        use_alpha: bool = Form(False),
        resolution: str = Form("1024"),
        simplify: bool = Form(True),
        reduce_ratio: float = Form(0.95),
    ) -> Dict[str, Any]:
        try:
            contents = await file.read()
            pil_image = Image.open(BytesIO(contents))
            pil_image.load()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image upload: {e}") from e

        if resolution not in {"256", "512", "1024"}:
            raise HTTPException(status_code=400, detail="resolution must be one of 256/512/1024")

        lock = request.app.state.d3d_lock
        sdf_res = int(resolution)
        service: Direct3DS2Service = await ensure_d3d_service(request.app.state, sdf_res)

        async with lock:
            try:
                mesh_path: Path = await run_in_threadpool(
                    service.generate_img2obj,
                    image=pil_image,
                    use_alpha=use_alpha,
                    resolution=resolution,
                    simplify=simplify,
                    reduce_ratio=reduce_ratio,
                    output_dir=mesh_dir,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Inference failed: {e}") from e

        mesh_id = mesh_path.stem
        mesh_url = request.url_for("d3d_mesh_obj", mesh_id=mesh_id)

        return {
            "mesh_id": mesh_id,
            "mesh_path": str(mesh_path),
            "mesh_url": str(mesh_url),
        }

    @router.delete("/meshes/{mesh_id}")
    async def delete_mesh(mesh_id: str) -> Dict[str, Any]:
        mesh_path = resolve_mesh_path(mesh_dir, mesh_id)
        if mesh_path is None:
            raise HTTPException(status_code=404, detail="Mesh not found")
        mesh_path.unlink()
        return {"deleted": mesh_id}

    return router
