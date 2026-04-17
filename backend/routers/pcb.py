from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from models.pcb2print3d.pipeline import convert_kicad_to_stl


def create_pcb_router(*, output_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/pcb", tags=["pcb2print3d"])

    @router.get("/models")
    def list_models() -> Dict[str, List[Dict[str, Any]]]:
        models: List[Dict[str, Any]] = []
        if output_dir.exists():
            for stl in sorted(output_dir.glob("*.stl"), key=lambda p: p.stat().st_mtime, reverse=True):
                models.append(
                    {
                        "model_id": stl.stem,
                        "filename": stl.name,
                        "updated_at": stl.stat().st_mtime,
                    }
                )
        return {"models": models}

    @router.get("/models/{model_id}.stl", name="pcb_stl_file")
    def get_model_file(model_id: str) -> FileResponse:
        path = output_dir / f"{model_id}.stl"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="STL not found")
        return FileResponse(
            str(path),
            media_type="model/stl",
            filename=path.name,
        )

    @router.post("/convert")
    async def convert(
        request: Request,
        file: UploadFile = File(...),
        thickness_mm: float = Form(1.6),
    ) -> Dict[str, Any]:
        if thickness_mm <= 0:
            raise HTTPException(status_code=400, detail="thickness_mm must be positive")
        if file.filename and not file.filename.lower().endswith(".kicad_pcb"):
            raise HTTPException(status_code=400, detail="Input file must be a .kicad_pcb file")

        try:
            contents = await file.read()
            if not contents:
                raise ValueError("uploaded file is empty")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid upload: {e}") from e

        model_id = uuid.uuid4().hex[:16]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{model_id}.stl"

        lock = request.app.state.pcb_lock
        with tempfile.TemporaryDirectory() as tmp:
            tmp_input = Path(tmp) / (file.filename or "board.kicad_pcb")
            tmp_input.write_bytes(contents)
            async with lock:
                try:
                    result = await run_in_threadpool(
                        convert_kicad_to_stl,
                        input_path=tmp_input,
                        output_path=output_path,
                        thickness_mm=thickness_mm,
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"PCB conversion failed: {e}") from e

        file_url = request.url_for("pcb_stl_file", model_id=model_id)
        return {
            "model_id": model_id,
            "filename": output_path.name,
            "model_url": str(file_url),
            "thickness_mm": result.thickness_mm,
            "holes": result.holes,
            "triangles": result.triangles,
            "outline_points": result.outline_points,
        }

    @router.delete("/models/{model_id}")
    async def delete_model(model_id: str) -> Dict[str, Any]:
        path = output_dir / f"{model_id}.stl"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="STL not found")
        path.unlink()
        return {"deleted": model_id}

    return router
