/**
 * Creates Three.js MeshViewers and assigns menu dispatchers.
 * Button handlers are wired synchronously in main.js (see app-handlers.js).
 */
import { $ } from "./core/dom.js";
import { MeshViewer } from "./ui/mesh-viewer.js";
import { setStatus } from "./ui/shell.js";
import { d3dViewerRef } from "./core/preview-refs.js";

/**
 * Attaches the 3D mesh viewer to `#viewport` (lazy-loaded module).
 */
export function initAppActions() {
  const viewportEl = $("#viewport");
  if (!viewportEl) {
    throw new Error("Missing #viewport");
  }

  d3dViewerRef.current = new MeshViewer(viewportEl, {
    onStatus: setStatus,
  });
}
