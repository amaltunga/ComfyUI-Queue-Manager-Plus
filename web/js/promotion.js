const COLORS = ["grey", "green", "orange", "red"];
const TITLES = {
  grey: "In the order it was queued",
  green: "Moved up 1 or 2 places",
  orange: "Moved up several places",
  red: "Moved to the front",
};

let colors = {};
let workflowColors = {};
let listening = false;
let refreshQueued = false;

export function installPromotion(app) {
  if (listening) return;
  listening = true;
  const refresh = () => scheduleRefresh();
  app.api.addEventListener("queue-manager-queue-updated", refresh);
  app.api.addEventListener("status", refresh);
  app.api.addEventListener("execution_start", refresh);
  app.api.addEventListener("execution_success", refresh);
}

export function bindPromotion(iframe) {
  if (!iframe || iframe.dataset.promotionBound === "1") return;
  iframe.dataset.promotionBound = "1";
  const hook = () => {
    watchRows(iframe);
    scheduleRefresh();
  };
  iframe.addEventListener("load", hook);
  if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") hook();
}

function watchRows(iframe) {
  const doc = iframe.contentDocument;
  if (!doc?.body || doc.body.dataset.promotionWatch === "1") return;
  doc.body.dataset.promotionWatch = "1";
  const observer = new MutationObserver(() => paint(iframe));
  observer.observe(doc.body, { childList: true, subtree: true });
  paint(iframe);
}

function scheduleRefresh() {
  if (refreshQueued) return;
  refreshQueued = true;
  setTimeout(async () => {
    refreshQueued = false;
    try {
      const [promotionResponse, workflowResponse] = await Promise.all([
        fetch("/queue_manager/promotion"),
        fetch("/queue_manager/workflow_colors"),
      ]);
      if (!promotionResponse.ok || !workflowResponse.ok) return;
      colors = await promotionResponse.json();
      workflowColors = await workflowResponse.json();
    } catch (error) {
      console.error("Could not read queue promotion colours:", error);
      return;
    }
    document.querySelectorAll(".comfyui-queue-manager iframe").forEach(paint);
  }, 150);
}

function rowId(row) {
  return row.getAttribute("data-qm-id") || row.getAttribute("data-reorder-id") || row.getAttribute("data-selection-id");
}

function paint(iframe) {
  const doc = iframe.contentDocument;
  if (!doc) return;
  const onQueue = !!doc.querySelector(".route-queue");
  doc.querySelectorAll("tr[data-qm-id], tr[data-reorder-id], tr[data-selection-id]").forEach((row) => {
    const id = rowId(row);
    const serial = row.querySelector("td.serial");
    if (serial) {
      let mark = serial.querySelector(".qm-promotion");
      if (!onQueue || !row.hasAttribute("data-reorder-id")) {
        mark?.remove();
      } else {
        const color = COLORS.includes(colors[id]) ? colors[id] : "grey";
        if (!mark) {
          mark = doc.createElement("span");
          mark.className = "qm-promotion";
          serial.prepend(mark);
        }
        mark.className = `qm-promotion ${color}`;
        mark.title = TITLES[color];
      }
    }
    paintWorkflowBlock(doc, row, id);
  });
  paintSelectionHint(doc);
}

function paintWorkflowBlock(doc, row, id) {
  const nameCell = row.querySelector("td.name .name-cell") || row.querySelector("td.name");
  if (!nameCell) return;
  const color = workflowColors[id];
  let swatch = nameCell.querySelector(".qm-workflow-swatch");
  if (!color) {
    swatch?.remove();
    nameCell.style.background = "";
    return;
  }
  if (!swatch) {
    swatch = doc.createElement("span");
    swatch.className = "qm-workflow-swatch";
    nameCell.insertBefore(swatch, nameCell.firstChild);
  }
  swatch.style.background = color;
  swatch.title = "Same colour means the same workflow";
  nameCell.style.background = `${color}22`;
}

function paintSelectionHint(doc) {
  const tabs = doc.querySelector(".route-queue .tabs");
  if (!tabs) {
    doc.querySelector(".qm-select-hint")?.remove();
    return;
  }
  if (tabs.querySelector(".qm-select-hint")) return;
  const hint = doc.createElement("span");
  hint.className = "qm-select-hint";
  hint.textContent = "Drag across jobs to select them, then drag a handle to move that group.";
  tabs.append(hint);
}
