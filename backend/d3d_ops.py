from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def legacy_mesh_dir(mesh_dir: Path) -> Path:
    return mesh_dir.parent.parent / "meshes"


def list_mesh_entries(mesh_dir: Path) -> List[Dict[str, Any]]:
    meshes: List[Dict[str, Any]] = []
    seen: set[str] = set()
    paths: List[Path] = []
    if mesh_dir.exists():
        paths.extend(mesh_dir.glob("*.obj"))
    leg = legacy_mesh_dir(mesh_dir)
    if leg.exists() and leg != mesh_dir:
        paths.extend(leg.glob("*.obj"))
    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        stem = path.stem
        if stem in seen:
            continue
        seen.add(stem)
        meshes.append(
            {
                "mesh_id": stem,
                "updated_at": path.stat().st_mtime,
                "filename": path.name,
            }
        )
    return meshes


def resolve_mesh_path(mesh_dir: Path, mesh_id: str) -> Path | None:
    for base in (mesh_dir, legacy_mesh_dir(mesh_dir)):
        p = base / f"{mesh_id}.obj"
        if p.exists():
            return p
    return None
