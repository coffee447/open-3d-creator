from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


def _nvidia_smi_gpu() -> Optional[Dict[str, float]]:
    """Parse nvidia-smi for GPU util % and VRAM MiB (first GPU)."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
        line = out.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            return None
        util = float(parts[0])
        mem_used = float(parts[1])
        mem_total = float(parts[2])
        return {"gpu_percent": util, "vram_used_mib": mem_used, "vram_total_mib": mem_total}
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, IndexError):
        return None


def _torch_vram_fallback() -> Optional[Dict[str, float]]:
    try:
        import torch

        if not torch.cuda.is_available():
            return None
        free_b, total_b = torch.cuda.mem_get_info()
        used_mib = (total_b - free_b) / (1024 * 1024)
        total_mib = total_b / (1024 * 1024)
        return {
            "gpu_percent": None,
            "vram_used_mib": used_mib,
            "vram_total_mib": total_mib,
        }
    except Exception:
        return None


def collect_system_metrics() -> Dict[str, Any]:
    """CPU %, RAM % and MiB, optional GPU util % and VRAM MiB."""
    out: Dict[str, Any] = {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mib": None,
        "memory_total_mib": None,
        "gpu_percent": None,
        "vram_used_mib": None,
        "vram_total_mib": None,
    }

    if psutil is not None:
        # interval>0 blocks briefly but returns a real sample (first call with interval=0 is often meaningless)
        out["cpu_percent"] = round(psutil.cpu_percent(interval=0.1), 1)
        vm = psutil.virtual_memory()
        out["memory_percent"] = round(vm.percent, 1)
        out["memory_used_mib"] = round(vm.used / (1024 * 1024), 0)
        out["memory_total_mib"] = round(vm.total / (1024 * 1024), 0)

    gpu = _nvidia_smi_gpu()
    if gpu is not None:
        out["gpu_percent"] = round(gpu["gpu_percent"], 1) if gpu["gpu_percent"] is not None else None
        out["vram_used_mib"] = round(gpu["vram_used_mib"], 0)
        out["vram_total_mib"] = round(gpu["vram_total_mib"], 0)
    else:
        fb = _torch_vram_fallback()
        if fb is not None:
            out["gpu_percent"] = fb.get("gpu_percent")
            out["vram_used_mib"] = round(fb["vram_used_mib"], 0) if fb.get("vram_used_mib") is not None else None
            out["vram_total_mib"] = round(fb["vram_total_mib"], 0) if fb.get("vram_total_mib") is not None else None

    return out
