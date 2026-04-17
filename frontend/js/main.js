/**
 * Open 3D Creator — shell + app handlers wire immediately; Three.js viewers attach when bootstrap loads.
 */
import {
  initShell,
  wireNavigation,
  switchView,
  setStatus,
} from "./ui/shell.js";
import { initMetricsUI, toggleMetrics } from "./ui/metrics.js";
import { d3d, pcb, pix } from "./app/app-handlers.js";

const actions = {
  onToggleMetrics: toggleMetrics,
};

d3d.wireCreate();
d3d.wireLibrary();
pcb.wire();
pix.wire();

initShell(actions);
wireNavigation();
switchView("home");
initMetricsUI();

void import("./bootstrap-app.js")
  .then((m) => m.initAppActions())
  .catch((err) => {
    console.error(err);
    setStatus("Failed to load 3D viewers", String(err));
  });
