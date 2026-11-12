const state = {
  promptId: null,
  nodes: {},
  titles: new Map(),
  nodeTotal: 0,
  loadedFor: null,
};

let painting = false;
let paintQueued = false;
let listening = false;
let comfyApp = null;

export function installJobProgress(app) {
  comfyApp = app;
  if (listening) return;
  listening = true;

  app.api.addEventListener("execution_start", (event) => {
    const promptId = event.detail?.prompt_id;
    if (!promptId) return;
    state.promptId = promptId;
    state.nodes = {};
    rememberWorkflow(promptId);
    schedulePaint();
  });

  app.api.addEventListener("progress_state", (event) => {
    const detail = event.detail || {};
    if (!detail.nodes) return;
    state.promptId = detail.prompt_id || state.promptId;
    state.nodes = detail.nodes;
    if (state.promptId && state.loadedFor !== state.promptId) rememberWorkflow(state.promptId);
    schedulePaint();
  });

  app.api.addEventListener("progress", (event) => {
    const detail = event.detail || {};
    const nodeId = detail.node == null ? "" : String(detail.node);
    if (!nodeId) return;
    const current = state.nodes[nodeId] || {};
    state.nodes = {
      ...state.nodes,
      [nodeId]: {
        ...current,
        value: detail.value,
        max: detail.max,
        state: "running",
        node_id: nodeId,
        display_node_id: current.display_node_id || nodeId,
        prompt_id: detail.prompt_id || state.promptId,
      },
    };
    schedulePaint();
  });

  const clear = () => {
    state.nodes = {};
    schedulePaint();
  };
  app.api.addEventListener("execution_success", clear);
  app.api.addEventListener("execution_error", clear);
  app.api.addEventListener("execution_interrupted", clear);
}

export function bindJobProgress(iframe) {
  if (!iframe || iframe.dataset.jobProgressBound === "1") return;
  iframe.dataset.jobProgressBound = "1";
  const hook = () => watchProgress(iframe);
  iframe.addEventListener("load", hook);
  if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") hook();
}

export function installComfySkin(iframe) {
  if (!iframe || iframe.dataset.comfySkin === "1") return;
  iframe.dataset.comfySkin = "1";
  const apply = () => {
    const doc = iframe.contentDocument;
    if (!doc || !doc.head || doc.getElementById("qm-comfy-skin")) return;
    copyTheme(doc);
    const link = doc.createElement("link");
    link.id = "qm-comfy-skin";
    link.rel = "stylesheet";
    link.href = new URL("../styles/comfy-skin.css", import.meta.url).href;
    doc.head.appendChild(link);
    schedulePaint();
  };
  iframe.addEventListener("load", apply);
  if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") apply();
}

function watchProgress(iframe) {
  const doc = iframe.contentDocument;
  if (!doc || !doc.body || doc.body.dataset.jobProgressWatch === "1") return;
  doc.body.dataset.jobProgressWatch = "1";
  const observer = new MutationObserver(() => {
    const running = doc.querySelector("tr.running");
    const stage = doc.querySelector("tr.qm-stage-row");
    if (running && !stage && hasStages()) schedulePaint();
    if (!running && stage) stage.remove();
  });
  observer.observe(doc.body, { childList: true, subtree: true });
  schedulePaint();
}

function copyTheme(doc) {
  const from = getComputedStyle(document.documentElement);
  const root = doc.documentElement;
  for (let index = 0; index < from.length; index += 1) {
    const prop = from.item(index);
    if (prop && prop.startsWith("--")) {
      root.style.setProperty(prop, from.getPropertyValue(prop));
    }
  }
}

async function rememberWorkflow(promptId) {
  state.loadedFor = promptId;
  try {
    const response = await fetch("/queue_manager/queue?route=queue&page=0&page_size=20");
    if (!response.ok) return;
    const data = await response.json();
    const jobs = [...(data.running || []), ...(data.pending || [])];
    const job = jobs.find((item) => item?.[1] === promptId) || (data.running || [])[0];
    const nodes = job?.[3]?.extra_pnginfo?.workflow?.nodes;
    if (!Array.isArray(nodes)) return;
    state.titles = new Map();
    let count = 0;
    for (const node of nodes) {
      if (node?.mode === 2 || node?.mode === 4) continue;
      count += 1;
      state.titles.set(String(node.id), node.title || node.type || String(node.id));
    }
    state.nodeTotal = count;
    schedulePaint();
  } catch (error) {
    console.error("Could not read workflow stage names:", error);
  }
}

function hasStages() {
  return Object.keys(state.nodes).length > 0;
}

function schedulePaint() {
  if (paintQueued) return;
  paintQueued = true;
  requestAnimationFrame(() => {
    paintQueued = false;
    paint();
  });
}

function paint() {
  if (painting) return;
  const iframe = document.querySelector(".comfyui-queue-manager iframe");
  const doc = iframe?.contentDocument;
  if (!doc) return;
  const running = doc.querySelector("tr.running");
  let row = doc.querySelector("tr.qm-stage-row");
  if (!running || !hasStages()) {
    row?.remove();
    return;
  }
  painting = true;
  try {
    if (!row) {
      row = doc.createElement("tr");
      row.className = "qm-stage-row";
      const cell = doc.createElement("td");
      cell.colSpan = 100;
      row.append(cell);
      running.after(row);
    }
    row.querySelector("td").replaceChildren(renderStages(doc));
  } finally {
    painting = false;
  }
}

function renderStages(doc) {
  const root = doc.createElement("div");
  root.className = "qm-stages";
  const entries = Object.values(state.nodes);
  const running = entries.filter((node) => node.state === "running");
  const finished = entries.filter((node) => node.state === "finished");
  root.append(stageLine(doc, "Total", overallPercent(entries, finished.length, running), "total"));
  for (const node of running) {
    root.append(stageLine(doc, stageName(node), stagePercent(node), "running"));
  }
  if (finished.length) {
    const names = finished.slice(-3).map(stageName).join(", ");
    const done = doc.createElement("div");
    done.className = "qm-stage-done";
    done.textContent = finished.length === 1 ? `${names} done` : `${finished.length} stages done · ${names}`;
    root.append(done);
  }
  return root;
}

function stageLine(doc, name, percent, kind) {
  const line = doc.createElement("div");
  line.className = `qm-stage ${kind}`;
  const label = doc.createElement("span");
  label.className = "qm-stage-name";
  label.textContent = name;
  label.title = name;
  const value = doc.createElement("span");
  value.className = "qm-stage-pct";
  value.textContent = `${percent}%`;
  const bar = doc.createElement("div");
  bar.className = "qm-stage-bar";
  const fill = doc.createElement("span");
  fill.style.width = `${percent}%`;
  bar.append(fill);
  line.append(label, value, bar);
  return line;
}

function overallPercent(entries, finishedCount, running) {
  const runningFraction = running.reduce((sum, node) => sum + stagePercent(node) / 100, 0);
  const done = finishedCount + runningFraction;
  if (state.nodeTotal > 0) {
    return Math.max(0, Math.min(100, Math.round((done / state.nodeTotal) * 100)));
  }
  if (!entries.length) return 0;
  const average = entries.reduce((sum, node) => sum + stagePercent(node), 0) / entries.length;
  return Math.round(average);
}

function stagePercent(node) {
  if (node.state === "finished" || node.state === "error") return node.state === "finished" ? 100 : 0;
  const max = Number(node.max);
  const value = Number(node.value);
  if (!Number.isFinite(max) || max <= 0 || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, Math.round((value / max) * 100)));
}

function stageName(node) {
  const id = String(node.display_node_id || node.node_id || "");
  if (state.titles.has(id)) return state.titles.get(id);
  const graph = comfyApp?.graph;
  const found = graph?.getNodeById?.(id) || graph?.getNodeById?.(Number(id));
  return found?.title || found?.type || `Node ${id}`;
}
