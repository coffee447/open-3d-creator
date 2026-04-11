import { $ } from "../core/dom.js";

const INTERVAL_MS = 2000;
const METRICS_URL = "/api/v1/system/metrics";
const STORAGE_KEY = "3dcreate_show_metrics";

/** @type {ReturnType<typeof setTimeout> | null} */
let pollTimer = null;

export function isMetricsEnabled() {
  return localStorage.getItem(STORAGE_KEY) === "true";
}

function setStored(enabled) {
  if (enabled) localStorage.setItem(STORAGE_KEY, "true");
  else localStorage.removeItem(STORAGE_KEY);
}

/**
 * @param {number | null | undefined} n
 * @param {number} [digits]
 */
function fmtPct(n, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  return `${Number(n).toFixed(digits)}%`;
}

function fmtGiBPair(used, total) {
  if (used == null || total == null) return "—";
  const u = used / 1024;
  const t = total / 1024;
  return `${u.toFixed(1)} / ${t.toFixed(1)} GB`;
}

async function fetchAndUpdate() {
  try {
    const res = await fetch(METRICS_URL);
    if (!res.ok) return;
    const m = await res.json();

    const elCpu = $("#status-cpu");
    const elMem = $("#status-mem");
    const elGpu = $("#status-gpu");
    const elVram = $("#status-vram");

    if (elCpu) {
      elCpu.textContent = m.cpu_percent != null ? `CPU ${fmtPct(m.cpu_percent)}` : "CPU —";
    }
    if (elMem) {
      if (m.memory_percent != null && m.memory_used_mib != null && m.memory_total_mib != null) {
        elMem.textContent = `RAM ${fmtPct(m.memory_percent)} (${fmtGiBPair(m.memory_used_mib, m.memory_total_mib)})`;
      } else {
        elMem.textContent = "RAM —";
      }
    }
    if (elGpu) {
      elGpu.textContent = m.gpu_percent != null ? `GPU ${fmtPct(m.gpu_percent)}` : "GPU —";
    }
    if (elVram) {
      elVram.textContent =
        m.vram_used_mib != null && m.vram_total_mib != null
          ? `VRAM ${fmtGiBPair(m.vram_used_mib, m.vram_total_mib)}`
          : "VRAM —";
    }
  } catch {
    /* ignore */
  }
}

function stopPolling() {
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function scheduleNext() {
  if (!isMetricsEnabled()) return;
  pollTimer = setTimeout(async () => {
    if (!isMetricsEnabled()) return;
    await fetchAndUpdate();
    scheduleNext();
  }, INTERVAL_MS);
}

function startPolling() {
  stopPolling();
  if (!isMetricsEnabled()) return;
  void fetchAndUpdate();
  scheduleNext();
}

function applyMetricsVisibility(enabled) {
  const group = $("#status-metrics-group");
  if (group) {
    group.classList.toggle("hidden", !enabled);
    group.setAttribute("aria-hidden", enabled ? "false" : "true");
  }
}

function updateMenuCheckmarks(enabled) {
  document.querySelectorAll(".menu-metrics-toggle").forEach((btn) => {
    btn.setAttribute("aria-checked", enabled ? "true" : "false");
    const check = btn.querySelector(".menu-check");
    if (check) check.textContent = enabled ? "✓" : "\u00a0";
  });
}

export function initMetricsUI() {
  const enabled = isMetricsEnabled();
  applyMetricsVisibility(enabled);
  updateMenuCheckmarks(enabled);
  if (enabled) startPolling();
}

export function toggleMetrics() {
  const next = !isMetricsEnabled();
  setStored(next);
  applyMetricsVisibility(next);
  updateMenuCheckmarks(next);
  if (next) startPolling();
  else stopPolling();
}

/** @deprecated Use initMetricsUI */
export function startSystemMetrics() {
  initMetricsUI();
}
