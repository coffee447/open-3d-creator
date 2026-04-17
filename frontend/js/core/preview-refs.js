/**
 * MeshViewer instances are created asynchronously after Three.js loads.
 * Handlers wire synchronously and read these refs when running.
 * @type {{ current: import("../ui/mesh-viewer.js").MeshViewer | null }}
 */
export const d3dViewerRef = { current: null };

/**
 * @type {{ current: import("../ui/mesh-viewer.js").MeshViewer | null }}
 */
export const pcbViewerRef = { current: null };
