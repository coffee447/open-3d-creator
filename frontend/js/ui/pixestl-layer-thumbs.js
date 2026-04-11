/**
 * Backward-compatible PIXEstL layer renderer for older cached frontend bundles.
 * New UI code does not rely on this module, but keeping it avoids runtime import errors.
 */

/**
 * @param {unknown} value
 * @returns {Array<Record<string, any>>}
 */
function toLayerArray(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") {
    const obj = /** @type {Record<string, any>} */ (value);
    if (Array.isArray(obj.layers)) return obj.layers;
    if (Array.isArray(obj.items)) return obj.items;
  }
  return [];
}

/**
 * @param {unknown} value
 * @returns {boolean}
 */
function isDomElement(value) {
  return value instanceof HTMLElement;
}

/**
 * @param {Record<string, any>} layer
 * @returns {string}
 */
function pickLayerName(layer) {
  const raw =
    layer.filename ||
    layer.name ||
    layer.layer_name ||
    layer.id ||
    layer.file ||
    "layer";
  if (typeof raw === "string" || typeof raw === "number") return String(raw);
  if (raw && typeof raw === "object") {
    const obj = /** @type {Record<string, any>} */ (raw);
    const nested = obj.filename || obj.name || obj.id || obj.path;
    if (typeof nested === "string" || typeof nested === "number") return String(nested);
  }
  return "layer";
}

/**
 * @param {Record<string, any>} layer
 * @returns {string | null}
 */
function pickLayerUrl(layer) {
  const raw = layer.url || layer.href || layer.download_url || layer.preview_url || layer.file;
  if (typeof raw === "string") return raw;
  if (raw && typeof raw === "object") {
    const obj = /** @type {Record<string, any>} */ (raw);
    const nested = obj.url || obj.href || obj.download_url || obj.preview_url || obj.path;
    return typeof nested === "string" ? nested : null;
  }
  return null;
}

/**
 * Render layer links/thumbnails in a container.
 * Accepts several historical call shapes:
 *  - renderPixestlLayerThumbs(container, layers)
 *  - renderPixestlLayerThumbs({ container, layers })
 *
 * @param {HTMLElement | { container?: HTMLElement | null; layers?: unknown }} target
 * @param {unknown} [maybeLayers]
 * @returns {void}
 */
export function renderPixestlLayerThumbs(target, maybeLayers) {
  /** @type {HTMLElement | null} */
  let container = null;
  let layersInput = undefined;

  // Signature: (container, layers)
  if (isDomElement(target)) {
    container = target;
    layersInput = maybeLayers;
  // Signature: (layers, container) from older bundle variants
  } else if (isDomElement(maybeLayers)) {
    container = maybeLayers;
    layersInput = target;
  // Signature: ({ container, layers })
  } else if (target && typeof target === "object") {
    const obj = /** @type {{ container?: HTMLElement | null; layers?: unknown }} */ (target);
    container = obj.container || null;
    layersInput = obj.layers;
  }

  if (!container) return;
  const layers = toLayerArray(layersInput);

  // Ignore undefined payloads so a second "empty" callback does not wipe good content.
  if (layersInput === undefined) return;

  container.innerHTML = "";
  if (!layers.length) {
    const p = document.createElement("p");
    p.className = "text-muted";
    p.textContent = "No layer files available.";
    container.appendChild(p);
    return;
  }

  for (const layer of layers) {
    const row = document.createElement("div");
    row.className = "pix-preview-block";

    const name = pickLayerName(layer);
    const url = pickLayerUrl(layer);
    const cap = document.createElement("code");
    cap.className = "pix-preview-filename";
    cap.textContent = String(name);
    row.appendChild(cap);

    if (url) {
      const link = document.createElement("a");
      link.href = String(url);
      link.textContent = " open";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      row.appendChild(link);

      if (String(name).toLowerCase().endsWith(".png")) {
        const img = document.createElement("img");
        img.className = "pix-preview-img";
        img.alt = String(name);
        img.loading = "lazy";
        img.decoding = "async";
        img.src = String(url);
        row.appendChild(img);
      }
    }

    container.appendChild(row);
  }
}

export const renderLayerThumbs = renderPixestlLayerThumbs;
export default renderPixestlLayerThumbs;
