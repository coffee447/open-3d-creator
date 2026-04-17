import { $ } from "../core/dom.js";
import {
  pcb,
  deletePcbModel,
  fetchPcbModels,
  postPcbConvert,
} from "../core/api.js";
import { setStatus, switchView } from "../ui/shell.js";

/**
 * @param {{ viewerRef: { current: import("../ui/mesh-viewer.js").MeshViewer | null } }} ctx
 */
export function createPcbHandlers(ctx) {
  const { viewerRef } = ctx;

  function getViewerOrWarn() {
    const v = viewerRef.current;
    if (!v) {
      setStatus("PCB preview still loading — try again in a moment", null);
      return null;
    }
    return v;
  }

  async function runConvert() {
    const input = $("#pcb-file-input");
    const file = input?.files?.[0];
    if (!file) {
      setStatus("Choose a .kicad_pcb file first", null);
      return;
    }
    const thickness = parseFloat($("#pcb-thickness")?.value || "1.6");
    if (!Number.isFinite(thickness) || thickness <= 0) {
      setStatus("Thickness must be a positive number", null);
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("thickness_mm", String(thickness));

    const btn = $("#btn-pcb-convert");
    if (btn) btn.disabled = true;
    setStatus("Converting PCB to STL…", "pcb2print3d");
    try {
      const data = await postPcbConvert(fd);
      const dl = $("#pcb-last-download");
      if (dl && data.model_url) {
        dl.href = data.model_url;
        dl.textContent = `Download ${data.filename || `${data.model_id}.stl`}`;
        dl.classList.remove("hidden");
      }
      const viewer = getViewerOrWarn();
      if (viewer && data.model_url) {
        viewer.ensure();
        viewer.loadStlUrl(data.model_url);
      }
      await refreshModels(data.model_id);
      switchView("pcb");
      setStatus("PCB conversion done", data.model_id || "");
    } catch (e) {
      console.error(e);
      setStatus("PCB conversion error", e.message || String(e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function refreshModels(preferredModelId) {
    const list = $("#pcb-model-list");
    if (!list) return;
    list.innerHTML = "";
    setStatus("Loading PCB STL files…", "pcb2print3d");
    try {
      const data = await fetchPcbModels();
      const models = data.models || [];
      models.forEach((m) => {
        const li = document.createElement("li");
        li.setAttribute("role", "option");
        li.className = "pcb-model-item";
        li.addEventListener("click", () => {
          const viewer = getViewerOrWarn();
          if (!viewer) return;
          list.querySelectorAll("li").forEach((x) => x.classList.remove("active"));
          li.classList.add("active");
          viewer.ensure();
          viewer.loadStlUrl(pcb.modelStl(m.model_id));
          setStatus("Loading PCB STL preview…", m.model_id);
        });

        const link = document.createElement("a");
        link.href = pcb.modelStl(m.model_id);
        link.textContent = m.filename || `${m.model_id}.stl`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.addEventListener("click", (ev) => {
          ev.preventDefault();
          li.click();
        });

        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn-primary";
        del.textContent = "Delete";
        del.addEventListener("click", async (ev) => {
          ev.preventDefault();
          ev.stopPropagation();
          try {
            await deletePcbModel(m.model_id);
            setStatus("Deleted PCB STL", m.model_id);
            await refreshModels();
          } catch (err) {
            console.error(err);
            setStatus("Delete failed", err.message || String(err));
          }
        });

        li.appendChild(link);
        li.appendChild(del);
        if (preferredModelId && preferredModelId === m.model_id) {
          li.classList.add("active");
        }
        list.appendChild(li);
      });
      setStatus(`Ready — PCB models (${models.length})`, "pcb2print3d");
    } catch (e) {
      console.error(e);
      setStatus("PCB list error", e.message || String(e));
    }
  }

  function wire() {
    $("#btn-pcb-convert")?.addEventListener("click", runConvert);
    $("#btn-pcb-refresh")?.addEventListener("click", () => refreshModels());
    $("#pcb-file-input")?.addEventListener("change", () => {
      $("#pcb-last-download")?.classList.add("hidden");
    });
  }

  return { wire, runConvert, refreshModels };
}
