import { $ } from "../core/dom.js";
import {
  pixestl,
  postPixestlGenerate,
  postPixestlExportZip,
  fetchPixestlExports,
} from "../core/api.js";
import { setStatus, switchView } from "../ui/shell.js";

const PIX_PREVIEW_SPECS = [
  {
    filename: "image-color-preview.png",
    description: "Quantized color",
  },
  {
    filename: "image-texture-preview.png",
    description: "Texture (heightmap source)",
  },
];

const PIX_PREVIEW_MAX_RETRIES = 5;
const PIX_PREVIEW_RETRY_DELAY_MS = 300;

export function createPixestlHandlers() {

  /** @type {string | null} */
  let currentExportId = null;

  function setCurrentExportId(exportId) {
    currentExportId = exportId;
    const exportBtn = $("#btn-pixestl-export-zip");
    if (exportBtn) exportBtn.disabled = !exportId;
  }

  /**
   * @param {string} exportId
   * @param {{ filename: string; description: string }} spec
   */
  function appendPreviewImg(exportId, spec) {
    const wrap = document.createElement("div");
    wrap.className = "pix-preview-block";
    const cap = document.createElement("div");
    cap.className = "pix-preview-caption";
    const sub = document.createElement("div");
    sub.className = "pix-preview-desc";
    sub.textContent = spec.description;
    cap.appendChild(sub);
    wrap.appendChild(cap);
    const url =
      new URL(pixestl.previewPngUrl(exportId, spec.filename), window.location.origin).href +
      "?t=" +
      Date.now();
    const img = document.createElement("img");
    img.className = "pix-preview-img";
    img.alt = spec.filename;
    img.loading = "lazy";
    img.decoding = "async";
    let attempts = 0;
    img.src = url;
    img.addEventListener("error", () => {
      attempts += 1;
      if (attempts <= PIX_PREVIEW_MAX_RETRIES) {
        window.setTimeout(() => {
          img.src = `${url}&retry=${attempts}`;
        }, PIX_PREVIEW_RETRY_DELAY_MS);
        return;
      }
      const miss = document.createElement("p");
      miss.className = "text-muted pix-preview-missing";
      miss.textContent = `Not available (${spec.filename}).`;
      img.replaceWith(miss);
    });
    wrap.appendChild(img);
    return wrap;
  }

  async function loadLayerPreviewsFor(exportId) {
    setCurrentExportId(exportId);
    const panel = $("#pix-layer-panel");
    const grid = $("#pix-layer-grid");
    if (!panel || !grid) return;

    panel.classList.remove("hidden");

    grid.innerHTML = "";
    setStatus("Loading PNG previews…", "PIXEstL");
    try {
      for (const spec of PIX_PREVIEW_SPECS) {
        grid.appendChild(appendPreviewImg(exportId, spec));
      }
      setStatus("Ready — PIXEstL previews", "PIXEstL");
    } catch (e) {
      console.error(e);
      const p = document.createElement("p");
      p.className = "text-muted";
      p.textContent = e.message || String(e);
      grid.appendChild(p);
      setStatus("PIXEstL preview error", e.message || String(e));
    }
  }

  async function runExportZip() {
    if (!currentExportId) {
      setStatus("Generate a preview first", null);
      return;
    }
    const btn = $("#btn-pixestl-export-zip");
    if (btn) btn.disabled = true;
    setStatus("Building ZIP…", "PIXEstL");
    try {
      const data = await postPixestlExportZip(currentExportId);
      const link = $("#pix-last-download");
      if (link && data.zip_url) {
        link.href = data.zip_url;
        link.classList.remove("hidden");
        link.textContent = `Download ${currentExportId}.zip`;
      }
      setStatus("ZIP ready", currentExportId);
      await refreshExports(currentExportId ?? undefined);
    } catch (e) {
      console.error(e);
      setStatus("Export ZIP error", e.message || String(e));
    } finally {
      if (btn) btn.disabled = !currentExportId;
    }
  }

  async function runGenerate() {
    const input = $("#pix-file-input");
    const file = input?.files?.[0];
    if (!file) {
      setStatus("Choose an image for PIXEstL", null);
      return;
    }

    const fd = new FormData();
    fd.append("file", file);
    const pal = $("#pix-palette-input")?.files?.[0];
    if (pal) fd.append("palette_file", pal);
    fd.append("dest_image_width", String(parseFloat($("#pix-width")?.value || "130")));
    fd.append("color_distance", $("#pix-color-dist")?.value || "CIELab");

    const btn = $("#btn-pixestl-generate");
    if (btn) btn.disabled = true;

    $("#pix-last-download")?.classList.add("hidden");

    setStatus("PIXEstL working…", "PIXEstL");
    try {
      const data = await postPixestlGenerate(fd);
      switchView("pixestl");
      setStatus("Loading PNG previews…", data.export_id || "");
      await loadLayerPreviewsFor(data.export_id);
      await refreshExports(data.export_id, true);
      $("#pix-layer-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      console.error(e);
      setStatus("PIXEstL error", e.message || String(e));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  /**
   * @param {string | undefined} [preferredExportId] If set and present, load PNG previews for this session first.
   * @param {boolean} [skipLayerLoad] If true, fetch exports only — skip reloading PNG previews (used right after Generate).
   */
  async function refreshExports(preferredExportId, skipLayerLoad) {
    setStatus("Loading exports…", "PIXEstL");
    try {
      const data = await fetchPixestlExports();
      const exports = data.exports || [];
      setStatus(`Ready — PIXEstL exports (${exports.length})`, "PIXEstL");
      if (exports.length && !skipLayerLoad) {
        const pick =
          preferredExportId &&
          exports.some((x) => x.export_id === preferredExportId)
            ? preferredExportId
            : exports[0].export_id;
        await loadLayerPreviewsFor(pick);
      } else if (!exports.length && !skipLayerLoad) {
        const panel = $("#pix-layer-panel");
        const grid = $("#pix-layer-grid");
        if (grid) {
          grid.innerHTML = "";
          const p = document.createElement("p");
          p.id = "pix-layer-placeholder";
          p.className = "text-muted pix-layer-placeholder";
          p.innerHTML = "Run <strong>Generate</strong> or <strong>Refresh</strong> to load previews.";
          grid.appendChild(p);
        }
        panel?.classList.remove("hidden");
        setCurrentExportId(null);
      }
    } catch (e) {
      console.error(e);
      setStatus("PIXEstL list error", e.message || String(e));
    }
  }

  function wire() {
    $("#btn-pixestl-generate")?.addEventListener("click", runGenerate);
    $("#btn-pixestl-export-zip")?.addEventListener("click", runExportZip);
    $("#btn-pixestl-refresh")?.addEventListener("click", () =>
      refreshExports(currentExportId ?? undefined)
    );
    const fileInput = /** @type {HTMLInputElement | null} */ ($("#pix-file-input"));
    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        const f = /** @type {HTMLInputElement} */ (e.target).files?.[0];
        const img = $("#pix-preview-img");
        const mainImg = $("#pix-main-source-preview");
        if (!img && !mainImg) return;
        if (!f) {
          img?.classList.add("hidden");
          mainImg?.classList.add("hidden");
          return;
        }
        const objectUrl = URL.createObjectURL(f);
        if (img) {
          img.src = objectUrl;
          img.classList.remove("hidden");
        }
        if (mainImg) {
          mainImg.src = objectUrl;
          mainImg.classList.remove("hidden");
        }
      });
    }
    setCurrentExportId(null);
    const panel = $("#pix-layer-panel");
    const grid = $("#pix-layer-grid");
    if (grid) {
      grid.innerHTML = "";
      const p = document.createElement("p");
      p.id = "pix-layer-placeholder";
      p.className = "text-muted pix-layer-placeholder";
      p.innerHTML = "Run <strong>Generate</strong> or <strong>Refresh</strong> to load previews.";
      grid.appendChild(p);
    }
    panel?.classList.remove("hidden");
  }

  return { runGenerate, refreshExports, loadLayerPreviewsFor, runExportZip, wire };
}
