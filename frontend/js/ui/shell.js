import { $ } from "../core/dom.js";

export const VIEWS = ["home", "d3d", "d3d-lib", "pixestl", "settings"];

/** @type {string} */
let currentView = "home";

export function getCurrentView() {
  return currentView;
}

/**
 * @param {string | null} left
 * @param {string | null} [right]
 */
export function setStatus(left, right) {
  const elL = $("#status-left");
  const elR = $("#status-right");
  if (elL && left != null) elL.textContent = left;
  if (elR && right != null) elR.textContent = right;
}

let openMenuId = null;

export function closeAllMenus() {
  document.querySelectorAll(".menu-panel").forEach((p) => p.classList.add("hidden"));
  document.querySelectorAll(".menu-btn").forEach((b) => b.setAttribute("aria-expanded", "false"));
  $("#menu-backdrop")?.remove();
  openMenuId = null;
}

function openMenu(id) {
  closeAllMenus();
  const panel = $(`#menu-${id}`);
  const btn = $(`[data-menu="${id}"]`);
  if (!panel || !btn) return;
  panel.classList.remove("hidden");
  btn.setAttribute("aria-expanded", "true");
  openMenuId = id;
  const backdrop = document.createElement("div");
  backdrop.id = "menu-backdrop";
  backdrop.className = "menu-backdrop";
  backdrop.addEventListener("click", closeAllMenus);
  document.body.appendChild(backdrop);
}

function toggleMenu(id) {
  if (openMenuId === id) closeAllMenus();
  else openMenu(id);
}

export function showAbout() {
  $("#modal-overlay")?.classList.remove("hidden");
}

export function hideAbout() {
  $("#modal-overlay")?.classList.add("hidden");
}

/**
 * @param {string} view
 */
export function switchView(view) {
  if (!VIEWS.includes(view)) return;
  currentView = view;

  document.querySelectorAll("[data-view-panel]").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-view-panel") === view);
  });

  document.querySelectorAll(".side-section").forEach((s) => {
    const id = s.id.replace("side-", "");
    s.classList.toggle("hidden", id !== view);
  });

  const vpSection = $("#viewport-section");
  if (vpSection) {
    const showVp = view === "d3d" || view === "d3d-lib";
    vpSection.classList.toggle("hidden", !showVp);
  }

  const labels = {
    home: "Home",
    d3d: "Direct3D-S2",
    "d3d-lib": "Direct3D-S2 — Meshes",
    pixestl: "PIXEstL",
    settings: "Settings",
  };
  const tool = view.startsWith("d3d") ? "Direct3D-S2" : view === "pixestl" ? "PIXEstL" : "Open 3D Creator";
  setStatus(`Ready — ${labels[view] || view}`, tool);
}

/**
 * @param {{
 *   onToggleMetrics?: () => void;
 * }} actions
 */
export function initShell(actions) {
  document.querySelectorAll(".menu-btn[data-menu]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMenu(btn.getAttribute("data-menu"));
    });
  });

  /** One delegated handler so clicks on inner nodes (e.g. .menu-check) still resolve the row. */
  $("#menubar")?.addEventListener("click", (e) => {
    const n = e.target;
    if (!(n instanceof Node)) return;
    const el = n instanceof Element ? n : n.parentElement;
    const item = el?.closest(".menu-panel .menu-item") ?? null;
    if (!item) return;
    if (item.classList.contains("menu-item-submenu")) return;
    const raw = item.getAttribute("data-action");
    const action = raw == null || raw === "" ? null : raw.trim();
    const isMetrics =
      action === "toggle-metrics" || item.classList.contains("menu-metrics-toggle");
    if (isMetrics) {
      e.preventDefault();
      closeAllMenus();
      if (typeof actions.onToggleMetrics === "function") {
        actions.onToggleMetrics();
      }
      return;
    }
    if (action === "nav") {
      const view = item.getAttribute("data-view");
      if (view) switchView(view);
      closeAllMenus();
      return;
    }
    if (action === "about") {
      closeAllMenus();
      showAbout();
      return;
    }
    if (action === "exit") {
      setStatus("Exit is not available in the browser", null);
      closeAllMenus();
      return;
    }
    setStatus(`${item.textContent.trim()} (not available)`, null);
    closeAllMenus();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllMenus();
      hideAbout();
    }
  });

  $("#about-ok")?.addEventListener("click", hideAbout);
  $("#modal-overlay")?.addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") hideAbout();
  });
}

export function wireNavigation() {
  document.querySelectorAll("[data-view]").forEach((el) => {
    if (el.closest(".menu-panel")) return;
    const v = el.getAttribute("data-view");
    if (!v) return;
    el.addEventListener("click", () => switchView(v));
  });
}
