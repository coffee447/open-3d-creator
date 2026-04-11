/** @param {string} sel @param {ParentNode} [root] */
export function $(sel, root = document) {
  return root.querySelector(sel);
}

/** @param {string} sel @param {ParentNode} [root] */
export function $$(sel, root = document) {
  return [...root.querySelectorAll(sel)];
}
