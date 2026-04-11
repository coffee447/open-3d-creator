from __future__ import annotations

import shutil
import tempfile
import uuid
import zipfile
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from PIL import Image

from ..services.pixestl_service import (
    DEFAULT_PALETTE,
    generate_layer_preview,
    pack_session_dir_to_zip,
)

ExportSource = Tuple[str, Path]

_PREVIEW_PNG_NAMES = frozenset({"image-color-preview.png", "image-texture-preview.png"})


def _resolve_export(session_dir: Path, export_dir: Path, export_id: str) -> ExportSource:
    """Return ``(\"dir\", session_path)`` or ``(\"zip\", zip_path)``."""
    sd = session_dir / export_id
    if sd.is_dir():
        return ("dir", sd)
    zp = export_dir / f"{export_id}.zip"
    if zp.is_file():
        return ("zip", zp)
    raise HTTPException(status_code=404, detail="Export not found")


def create_pixestl_router(*, export_dir: Path, session_dir: Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/pixestl", tags=["pixestl"])

    @router.get("/exports")
    def list_exports() -> Dict[str, List[Dict[str, Any]]]:
        exports: List[Dict[str, Any]] = []
        seen: set[str] = set()

        if session_dir.exists():
            for d in sorted([p for p in session_dir.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True):
                eid = d.name
                seen.add(eid)
                zip_path = export_dir / f"{eid}.zip"
                exports.append(
                    {
                        "export_id": eid,
                        "updated_at": d.stat().st_mtime,
                        "has_zip": zip_path.is_file(),
                        "filename": f"{eid}.zip" if zip_path.is_file() else None,
                    }
                )

        if export_dir.exists():
            for zp in sorted(export_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
                eid = zp.stem
                if eid in seen:
                    continue
                exports.append(
                    {
                        "export_id": eid,
                        "updated_at": zp.stat().st_mtime,
                        "has_zip": True,
                        "filename": zp.name,
                    }
                )

        exports.sort(key=lambda x: x["updated_at"], reverse=True)
        return {"exports": exports}

    @router.get("/exports/{export_id}.zip", name="pixestl_zip", response_model=None)
    def get_export_zip(export_id: str) -> FileResponse:
        path = export_dir / f"{export_id}.zip"
        if not path.exists():
            raise HTTPException(status_code=404, detail="ZIP not found — use Export to ZIP after preview")
        return FileResponse(
            str(path),
            media_type="application/zip",
            filename=path.name,
        )

    @router.post("/exports/{export_id}/zip")
    async def build_export_zip(request: Request, export_id: str) -> Dict[str, Any]:
        """Pack the preview session folder into ``exports/{export_id}.zip``."""
        session_path = session_dir / export_id
        if not session_path.is_dir():
            raise HTTPException(status_code=404, detail="No preview session — run Generate first")
        dest_zip = export_dir / f"{export_id}.zip"
        export_dir.mkdir(parents=True, exist_ok=True)
        lock = request.app.state.pixestl_lock
        async with lock:
            await run_in_threadpool(
                pack_session_dir_to_zip,
                session_dir=session_path,
                dest_zip_path=dest_zip,
            )
        zip_url = request.url_for("pixestl_zip", export_id=export_id)
        return {
            "export_id": export_id,
            "zip_url": str(zip_url),
            "has_zip": True,
        }

    @router.get("/exports/{export_id}/preview/{filename}", response_model=None)
    def get_preview_png(export_id: str, filename: str) -> Response | FileResponse:
        """Serve ``image-color-preview.png`` or ``image-texture-preview.png`` from session dir or ZIP."""
        filename = unquote(filename)
        if filename not in _PREVIEW_PNG_NAMES:
            raise HTTPException(status_code=400, detail="Unknown preview file")

        kind, path = _resolve_export(session_dir, export_dir, export_id)
        if kind == "dir":
            target = path / filename
            if not target.is_file():
                raise HTTPException(status_code=404, detail="Preview not found")
            return FileResponse(
                str(target),
                media_type="image/png",
                filename=filename,
            )

        with zipfile.ZipFile(path) as zf:
            if filename not in zf.namelist():
                raise HTTPException(status_code=404, detail="Preview not in archive")
            data = zf.read(filename)
        return Response(content=data, media_type="image/png")

    @router.get("/exports/{export_id}/layers")
    def list_export_layers(request: Request, export_id: str) -> Dict[str, Any]:
        """
        Compatibility endpoint for older PIXEstL frontend code that expects
        `/exports/{export_id}/layers`.
        """
        kind, path = _resolve_export(session_dir, export_dir, export_id)
        if kind == "dir":
            names = {p.name for p in path.iterdir() if p.is_file()}
        else:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())

        layers = []
        layer_filenames = []
        for filename in sorted(_PREVIEW_PNG_NAMES):
            layer_url = request.url_for(
                "get_preview_png",
                export_id=export_id,
                filename=filename,
            )
            layer_filenames.append(filename)
            layers.append(
                {
                    "filename": filename,
                    "exists": filename in names,
                    "url": str(layer_url),
                }
            )

        return {
            "export_id": export_id,
            # Legacy clients expect an array of plain strings and then build
            # `/exports/{id}/layer/{filename}` links from each entry.
            "layers": layer_filenames,
            # Newer/compat clients can use richer metadata from this field.
            "layer_items": layers,
            "preview_pngs": layer_filenames,
            "preview_items": layers,
        }

    @router.get("/exports/{export_id}/layer/{filename}", response_model=None)
    def get_export_layer_file(export_id: str, filename: str) -> Response | FileResponse:
        """
        Legacy endpoint used by older frontend bundles to open/download a layer file.
        Serves top-level files from session dir or ZIP archive.
        """
        filename = unquote(filename)
        if "/" in filename or "\\" in filename or filename in {"", ".", ".."}:
            raise HTTPException(status_code=400, detail="Invalid filename")

        kind, path = _resolve_export(session_dir, export_dir, export_id)
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        if kind == "dir":
            target = path / filename
            if not target.is_file():
                raise HTTPException(status_code=404, detail="Layer file not found")
            return FileResponse(
                str(target),
                media_type=media_type,
                filename=filename,
            )

        with zipfile.ZipFile(path) as zf:
            if filename not in zf.namelist():
                raise HTTPException(status_code=404, detail="Layer file not in archive")
            data = zf.read(filename)
        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @router.get("/exports/{export_id}/layer/{filename}/thumb", response_model=None)
    def get_export_layer_thumb(export_id: str, filename: str) -> Response | FileResponse:
        """
        Legacy thumbnail endpoint alias. For preview PNG files this matches
        `/exports/{export_id}/preview/{filename}`.
        """
        filename = unquote(filename)
        if filename not in _PREVIEW_PNG_NAMES:
            raise HTTPException(status_code=404, detail="Thumbnail not available")
        return get_preview_png(export_id, filename)

    @router.post("/generate")
    async def generate(
        request: Request,
        file: UploadFile = File(...),
        palette_file: UploadFile | None = File(None),
        dest_image_width: float = Form(130.0),
        color_distance: str = Form("CIELab"),
    ) -> Dict[str, Any]:
        if color_distance not in {"RGB", "CIELab"}:
            raise HTTPException(status_code=400, detail="color_distance must be RGB or CIELab")
        if dest_image_width <= 0:
            raise HTTPException(status_code=400, detail="dest_image_width must be positive")

        try:
            contents = await file.read()
            Image.open(BytesIO(contents)).load()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from e

        export_id = uuid.uuid4().hex[:16]
        dest_session = session_dir / export_id
        session_dir.mkdir(parents=True, exist_ok=True)

        lock = request.app.state.pixestl_lock

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src_path = tmp_path / "source.png"
            src_path.write_bytes(contents)

            if palette_file and palette_file.filename:
                pal_bytes = await palette_file.read()
                pal_path = tmp_path / "palette.json"
                pal_path.write_bytes(pal_bytes)
                palette_path = pal_path
            else:
                if not DEFAULT_PALETTE.is_file():
                    raise HTTPException(
                        status_code=500,
                        detail=f"Default palette missing: {DEFAULT_PALETTE}",
                    )
                palette_path = DEFAULT_PALETTE

            async with lock:
                try:
                    await run_in_threadpool(
                        generate_layer_preview,
                        src_image_path=src_path,
                        palette_path=palette_path,
                        dest_image_width=dest_image_width,
                        dest_dir_path=dest_session,
                        color_distance=color_distance,  # type: ignore[arg-type]
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"PIXEstL failed: {e}") from e

        return {
            "export_id": export_id,
            "has_zip": False,
        }

    @router.delete("/exports/{export_id}")
    async def delete_export(export_id: str) -> Dict[str, Any]:
        session_path = session_dir / export_id
        zip_path = export_dir / f"{export_id}.zip"
        removed = False
        if session_path.is_dir():
            shutil.rmtree(session_path)
            removed = True
        if zip_path.is_file():
            zip_path.unlink()
            removed = True
        if not removed:
            raise HTTPException(status_code=404, detail="Export not found")
        return {"deleted": export_id}

    return router
