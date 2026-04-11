import { $ } from "../core/dom.js";
import { d3d, postD3dImg2Obj, fetchD3dMeshes } from "../core/api.js";
import { setStatus, switchView } from "../ui/shell.js";

/**
 * @param {{ viewerRef: { current: import("../ui/mesh-viewer.js").MeshViewer | null } }} ctx
 */
export function createD3dHandlers(ctx) {
  const { viewerRef } = ctx;

  function getViewerOrWarn() {
    const v = viewerRef.current;
    if (!v) {
      setStatus("3D viewer still loading — try again in a moment", null);
      return null;
    }
    return v;
  }

  async function runGenerate() {
    const input = $("#file-input");
    const file = input?.files?.[0];
    if (!file) {
      setStatus("Choose an image file first", null);
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("use_alpha", $("#use-alpha")?.checked ? "true" : "false");
    fd.append("resolution", $("#resolution")?.value || "1024");
    fd.append("simplify", $("#simplify")?.checked ? "true" : "false");
    fd.append("reduce_ratio", String(parseFloat($("#reduce-ratio")?.value || "0.95")));

    const btn = $("#btn-generate");
    if (btn) btn.disabled = true;

    setStatus("Working…", "Direct3D-S2");
    try {
      const data = await postD3dImg2Obj(fd);
      const meshUrl = data.mesh_url || d3d.meshObj(data.mesh_id);
      const viewer = getViewerOrWarn();
      if (!viewer) return;
      viewer.ensure();
      viewer.loadUrl(meshUrl);
      setStatus("Done", data.mesh_id || "");
    } catch (e) {
      console.error(e);
      setStatus("Error", e.message || String(e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function refreshMeshList() {
    const ul = $("#mesh-list");
    if (!ul) return;
    ul.innerHTML = "";
    setStatus("Loading meshes…", "Direct3D-S2");
    try {
      const data = await fetchD3dMeshes();
      const meshes = data.meshes || [];
      meshes.forEach((m) => {
        const li = document.createElement("li");
        li.textContent = m.filename || `${m.mesh_id}.obj`;
        li.dataset.meshId = m.mesh_id;
        li.setAttribute("role", "option");
        li.addEventListener("click", () => {
          ul.querySelectorAll("li").forEach((x) => x.classList.remove("active"));
          li.classList.add("active");
          switchView("d3d-lib");
          const viewer = getViewerOrWarn();
          if (!viewer) return;
          viewer.ensure();
          viewer.loadUrl(d3d.meshObj(m.mesh_id));
        });
        ul.appendChild(li);
      });
      setStatus(`Ready — D3D meshes (${meshes.length})`, "Direct3D-S2");
    } catch (e) {
      console.error(e);
      setStatus("Library error", e.message || String(e));
    }
  }

  function wireCreate() {
    $("#btn-generate")?.addEventListener("click", runGenerate);
    $("#file-input")?.addEventListener("change", (e) => {
      const f = /** @type {HTMLInputElement} */ (e.target).files?.[0];
      const img = $("#preview-img");
      if (!img) return;
      if (!f) {
        img.classList.add("hidden");
        return;
      }
      img.src = URL.createObjectURL(f);
      img.classList.remove("hidden");
    });
  }

  function wireLibrary() {
    $("#btn-refresh-lib")?.addEventListener("click", refreshMeshList);
  }

  return { runGenerate, refreshMeshList, wireCreate, wireLibrary };
}
