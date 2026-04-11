/** Direct3D-S2 (neural mesh) — separate namespace from PIXEstL. */
export const d3d = {
  img2obj: "/api/v1/d3d/mesh/img2obj",
  meshes: "/api/v1/d3d/meshes",
  meshObj: (id) => `/api/v1/d3d/meshes/${encodeURIComponent(id)}.obj`,
};

/** PIXEstL (PNG previews + STL outputs on disk / in ZIP) — separate tool. */
export const pixestl = {
  generate: "/api/v1/pixestl/generate",
  exports: "/api/v1/pixestl/exports",
  zipUrl: (id) => `/api/v1/pixestl/exports/${encodeURIComponent(id)}.zip`,
  exportZip: (id) => `/api/v1/pixestl/exports/${encodeURIComponent(id)}/zip`,
  previewPngUrl: (exportId, filename) =>
    `/api/v1/pixestl/exports/${encodeURIComponent(exportId)}/preview/${encodeURIComponent(filename)}`,
};

/**
 * @param {FormData} formData
 * @returns {Promise<{ mesh_id: string, mesh_url?: string, mesh_path?: string }>}
 */
export async function postD3dImg2Obj(formData) {
  const res = await fetch(d3d.img2obj, { method: "POST", body: formData });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json();
}

/** @returns {Promise<{ meshes: Array<{ mesh_id: string, filename?: string }> }>} */
export async function fetchD3dMeshes() {
  const res = await fetch(d3d.meshes);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * @param {FormData} formData
 * @returns {Promise<{ export_id: string, has_zip?: boolean }>}
 */
export async function postPixestlGenerate(formData) {
  const res = await fetch(pixestl.generate, { method: "POST", body: formData });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json();
}

/**
 * @param {string} exportId
 * @returns {Promise<{ export_id: string, zip_url: string, has_zip: boolean }>}
 */
export async function postPixestlExportZip(exportId) {
  const res = await fetch(pixestl.exportZip(exportId), { method: "POST" });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json();
}

/** @returns {Promise<{ exports: Array<{ export_id: string, filename?: string, has_zip?: boolean }> }>} */
export async function fetchPixestlExports() {
  const res = await fetch(pixestl.exports);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

