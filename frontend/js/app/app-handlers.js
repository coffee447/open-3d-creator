/**
 * D3D + PIXEstL handler instances (no Three.js — viewers come from preview-refs).
 */
import { createD3dHandlers } from "./generate.js";
import { createPcbHandlers } from "./pcb.js";
import { createPixestlHandlers } from "./pixestl.js";
import { createStep1x3dHandlers } from "./step1x3d.js";
import { d3dViewerRef, pcbViewerRef } from "../core/preview-refs.js";

export const d3d = createD3dHandlers({ viewerRef: d3dViewerRef });
export const pcb = createPcbHandlers({ viewerRef: pcbViewerRef });
export const pix = createPixestlHandlers();
export const step1x3d = createStep1x3dHandlers();
