from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from io import BytesIO
from PIL import Image

from .d3d_ops import list_mesh_entries, resolve_mesh_path
from .direct3d_s2_service import ensure_d3d_service
from .metrics import collect_system_metrics
from .routers.d3d import create_d3d_router
from .routers.pcb import create_pcb_router
from .routers.pixestl_rt import create_pixestl_router
from .routers.step1x3d import create_step1x3d_router
from .services.step1x3d_service import Step1X3DService

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = _PROJECT_ROOT / "frontend"
D3D_MESH_DIR = _PROJECT_ROOT / "outputs/d3d/meshes"
PIXESTL_EXPORT_DIR = _PROJECT_ROOT / "outputs/pixestl/exports"
PIXESTL_SESSION_DIR = _PROJECT_ROOT / "outputs/pixestl/sessions"
PCB_MODEL_DIR = _PROJECT_ROOT / "outputs/pcb/models"
STEP1X3D_MODEL_DIR = _PROJECT_ROOT / "outputs/step1x3d/models"

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    debug=True,
    title="Open 3D Creator",
    version="0.4.0",
    description="Direct3D-S2, PIXEstL, pcb2print3d, and Step1X-3D tools",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(create_d3d_router(mesh_dir=D3D_MESH_DIR))
app.include_router(
    create_pixestl_router(export_dir=PIXESTL_EXPORT_DIR, session_dir=PIXESTL_SESSION_DIR)
)
app.include_router(create_pcb_router(output_dir=PCB_MODEL_DIR))
app.include_router(create_step1x3d_router(output_dir=STEP1X3D_MODEL_DIR))


@app.on_event("startup")
async def _startup() -> None:
    project_root = _PROJECT_ROOT
    pipeline_pretrained_path = project_root / "weights/wushuang98/Direct3D-S2"
    subfolder = "direct3d-s2-v-1-1"

    D3D_MESH_DIR.mkdir(parents=True, exist_ok=True)
    PIXESTL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    PIXESTL_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    PCB_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    STEP1X3D_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    app.state.mesh_dir = D3D_MESH_DIR
    app.state.pixestl_export_dir = PIXESTL_EXPORT_DIR
    app.state.pixestl_session_dir = PIXESTL_SESSION_DIR
    app.state.pcb_model_dir = PCB_MODEL_DIR
    app.state.step1x3d_model_dir = STEP1X3D_MODEL_DIR
    # Lazy Direct3DS2Service: weights stay off GPU until first img2obj (see ensure_d3d_service).
    app.state.service = None
    app.state.d3d_device = "cuda:0"
    app.state.d3d_pipeline_pretrained_path = pipeline_pretrained_path
    app.state.d3d_subfolder = subfolder
    app.state.d3d_service_init_lock = asyncio.Lock()
    app.state.d3d_lock = asyncio.Lock()
    app.state.pixestl_lock = asyncio.Lock()
    app.state.pcb_lock = asyncio.Lock()
    app.state.step1x3d_lock = asyncio.Lock()
    app.state.step1x3d_service = Step1X3DService(project_root=project_root, device="cuda")


def _mesh_dir() -> Path:
    return app.state.mesh_dir


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/system/metrics")
async def system_metrics() -> Dict[str, Any]:
    """CPU, RAM, and optional NVIDIA GPU / VRAM (via nvidia-smi or PyTorch VRAM fallback)."""
    return await run_in_threadpool(collect_system_metrics)


# --- Legacy Direct3D API (same data as /api/v1/d3d/*) ---


@app.get("/api/v1/meshes")
def legacy_list_meshes() -> Dict[str, List[Dict[str, Any]]]:
    return {"meshes": list_mesh_entries(_mesh_dir())}


@app.get("/api/v1/meshes/{mesh_id}.obj", name="mesh_obj")
def legacy_get_mesh_obj(mesh_id: str, request: Request) -> FileResponse:
    mesh_path = resolve_mesh_path(_mesh_dir(), mesh_id)
    if mesh_path is None:
        raise HTTPException(status_code=404, detail="Mesh not found")
    return FileResponse(
        str(mesh_path),
        media_type="model/obj",
        filename=mesh_path.name,
    )


@app.post("/api/v1/direct3d_s2/img2obj")
async def legacy_img2obj_upload(
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

    service = await ensure_d3d_service(app.state, int(resolution))
    async with app.state.d3d_lock:
        try:
            mesh_path: Path = await run_in_threadpool(
                service.generate_img2obj,
                image=pil_image,
                use_alpha=use_alpha,
                resolution=resolution,
                simplify=simplify,
                reduce_ratio=reduce_ratio,
                output_dir=_mesh_dir(),
            )
        except Exception as e:
            logger.exception("Legacy direct3d_s2 img2obj failed")
            raise HTTPException(status_code=500, detail=f"Inference failed: {e}") from e

    mesh_id = mesh_path.stem
    mesh_url = request.url_for("mesh_obj", mesh_id=mesh_id)

    return {
        "mesh_id": mesh_id,
        "mesh_path": str(mesh_path),
        "mesh_url": str(mesh_url),
    }


@app.delete("/api/v1/meshes/{mesh_id}")
async def legacy_delete_mesh(mesh_id: str) -> Dict[str, Any]:
    mesh_path = resolve_mesh_path(_mesh_dir(), mesh_id)
    if mesh_path is None:
        raise HTTPException(status_code=404, detail="Mesh not found")
    mesh_path.unlink()
    return {"deleted": mesh_id}


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
