/**
 * D3D + PIXEstL handler instances (no Three.js — viewers come from preview-refs).
 */
import { createD3dHandlers } from "./generate.js";
import { createPixestlHandlers } from "./pixestl.js";
import { d3dViewerRef } from "../core/preview-refs.js";

export const d3d = createD3dHandlers({ viewerRef: d3dViewerRef });
export const pix = createPixestlHandlers();
