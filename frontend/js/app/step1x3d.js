import { $ } from "../core/dom.js";
import {
  deleteStep1x3dModel,
  fetchStep1x3dModels,
  postStep1x3dGenerate,
  step1x3d,
} from "../core/api.js";
import { setStatus, switchView } from "../ui/shell.js";

export function createStep1x3dHandlers() {
  async function runGenerate() {
    const input = $("#step1x-file-input");
    const file = input?.files?.[0];
    if (!file) {
      setStatus("Choose an input image first", null);
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    fd.append("guidance_scale", String(parseFloat($("#step1x-guidance")?.value || "7.5")));
    fd.append("num_inference_steps", String(parseInt($("#step1x-steps")?.value || "50", 10)));
    fd.append("seed", String(parseInt($("#step1x-seed")?.value || "2025", 10)));

    const btn = $("#btn-step1x-generate");
    if (btn) btn.disabled = true;
    setStatus("Step1X-3D generating GLB…", "Step1X-3D");
    try {
      const data = await postStep1x3dGenerate(fd);
      const dl = $("#step1x-last-download");
      if (dl) {
        dl.href = data.model_url;
        dl.textContent = `Download ${data.filename || `${data.model_id}.glb`}`;
        dl.classList.remove("hidden");
      }
      await refreshModels(data.model_id);
      switchView("step1x3d");
      setStatus("Step1X-3D done", data.model_id || "");
    } catch (e) {
      console.error(e);
      setStatus("Step1X-3D error", e.message || String(e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function refreshModels(preferredModelId) {
    const list = $("#step1x-model-list");
    if (!list) return;
    list.innerHTML = "";
    setStatus("Loading Step1X-3D outputs…", "Step1X-3D");
    try {
      const data = await fetchStep1x3dModels();
      const models = data.models || [];
      models.forEach((m) => {
        const li = document.createElement("li");
        li.className = "pcb-model-item";
        if (preferredModelId && preferredModelId === m.model_id) li.classList.add("active");

        const link = document.createElement("a");
        link.href = step1x3d.modelGlb(m.model_id);
        link.textContent = m.filename || `${m.model_id}.glb`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";

        const del = document.createElement("button");
        del.type = "button";
        del.className = "btn-primary";
        del.textContent = "Delete";
        del.addEventListener("click", async (ev) => {
          ev.preventDefault();
          try {
            await deleteStep1x3dModel(m.model_id);
            setStatus("Deleted Step1X-3D output", m.model_id);
            await refreshModels();
          } catch (err) {
            console.error(err);
            setStatus("Delete failed", err.message || String(err));
          }
        });

        li.appendChild(link);
        li.appendChild(del);
        list.appendChild(li);
      });
      setStatus(`Ready — Step1X-3D outputs (${models.length})`, "Step1X-3D");
    } catch (e) {
      console.error(e);
      setStatus("Step1X-3D list error", e.message || String(e));
    }
  }

  function wire() {
    $("#btn-step1x-generate")?.addEventListener("click", runGenerate);
    $("#btn-step1x-refresh")?.addEventListener("click", () => refreshModels());
    $("#step1x-file-input")?.addEventListener("change", () => {
      $("#step1x-last-download")?.classList.add("hidden");
    });
  }

  return { wire, runGenerate, refreshModels };
}
