const EDITOR_ID = "qm-job-fields-editor";

export function installJobFieldEditors(iframe) {
  if (!iframe || iframe.dataset.jobFieldsInstalled === "1") return;
  const hook = () => watchQueueRows(iframe);
  iframe.addEventListener("load", hook);
  if (iframe.contentDocument && iframe.contentDocument.readyState === "complete") hook();
  iframe.dataset.jobFieldsInstalled = "1";
}

function watchQueueRows(iframe) {
  const doc = iframe.contentDocument;
  if (!doc || !doc.body || doc.body.dataset.jobFieldsWatch === "1") return;
  doc.body.dataset.jobFieldsWatch = "1";
  const addButtons = () => {
    doc.querySelectorAll("tr[data-reorder-id]").forEach((row) => {
      if (row.querySelector(".job-fields-edit")) return;
      const actions = row.querySelector("td.actions .buttons");
      const dbId = row.getAttribute("data-reorder-id");
      if (!actions || !dbId) return;
      const button = doc.createElement("button");
      button.type = "button";
      button.className = "blue-button shiny-button job-fields-edit";
      button.textContent = "Edit";
      button.title = "Edit prompt and duration";
      button.setAttribute("data-selection-ignore", "true");
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openEditor(dbId);
      });
      actions.insertBefore(button, actions.firstChild);
    });
  };
  const observer = new MutationObserver(addButtons);
  observer.observe(doc.body, { childList: true, subtree: true });
  addButtons();
}

async function openEditor(dbId) {
  closeEditor();
  const overlay = document.createElement("div");
  overlay.id = EDITOR_ID;
  overlay.style.cssText = [
    "position:fixed",
    "inset:0",
    "z-index:10000",
    "background:rgba(0,0,0,0.55)",
    "display:flex",
    "align-items:center",
    "justify-content:center",
    "padding:24px",
  ].join(";");
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeEditor();
  });

  const panel = document.createElement("form");
  panel.style.cssText = [
    "width:min(640px, 100%)",
    "max-height:calc(100vh - 48px)",
    "overflow:auto",
    "background:var(--comfy-menu-bg, #202020)",
    "color:var(--fg-color, #ddd)",
    "border:1px solid rgba(255,255,255,0.16)",
    "border-radius:10px",
    "padding:16px",
    "display:flex",
    "flex-direction:column",
    "gap:10px",
    "box-shadow:0 16px 50px rgba(0,0,0,0.45)",
  ].join(";");
  panel.innerHTML = `<div style="font-weight:600">Edit queued job</div><div class="qm-job-status">Loading…</div>`;
  overlay.appendChild(panel);
  document.body.appendChild(overlay);

  const onKey = (event) => {
    if (event.key === "Escape") closeEditor();
  };
  document.addEventListener("keydown", onKey);
  overlay.dataset.bound = "1";
  overlay._onKey = onKey;

  let fields;
  try {
    const response = await fetch(`/queue_manager/job_fields?id=${encodeURIComponent(dbId)}`);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || `Could not load job (${response.status})`);
    fields = body;
  } catch (error) {
    panel.innerHTML = "";
    panel.append(heading("Edit queued job"), message(error.message || "Could not load this job"), closeButton());
    return;
  }

  panel.innerHTML = "";
  panel.append(heading(fields.name || "Edit queued job"));

  const promptBox = document.createElement("textarea");
  promptBox.rows = 8;
  promptBox.style.cssText = fieldStyle();
  promptBox.value = fields.prompt || "";
  promptBox.disabled = !fields.prompt_editable;
  if (fields.prompt_editable) {
    panel.append(label("Prompt"), promptBox);
  } else {
    panel.append(message("This job has no prompt box to edit."));
  }

  let durationBox = null;
  if (fields.duration_editable) {
    durationBox = document.createElement("input");
    durationBox.type = "number";
    durationBox.min = String(fields.duration_min);
    durationBox.max = String(fields.duration_max);
    durationBox.step = "0.5";
    durationBox.style.cssText = fieldStyle();
    durationBox.value = fields.duration == null ? "" : String(fields.duration);
    panel.append(label(`Duration (seconds, ${fields.duration_min}–${fields.duration_max})`), durationBox);
  }

  const status = message("");
  const actions = document.createElement("div");
  actions.style.cssText = "display:flex;gap:8px;justify-content:flex-end";
  const cancel = closeButton();
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "Save";
  save.style.cssText = buttonStyle("#3d7eff");
  actions.append(cancel, save);
  panel.append(status, actions);

  panel.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.textContent = "Saving…";
    save.disabled = true;
    const payload = { id: Number(dbId) };
    if (fields.prompt_editable) payload.prompt = promptBox.value;
    if (durationBox) payload.duration = Number(durationBox.value);
    try {
      const response = await fetch("/queue_manager/job_fields", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Save failed (${response.status})`);
      closeEditor();
    } catch (error) {
      status.textContent = error.message || "Save failed";
      save.disabled = false;
    }
  });
}

function closeEditor() {
  const overlay = document.getElementById(EDITOR_ID);
  if (!overlay) return;
  if (overlay._onKey) document.removeEventListener("keydown", overlay._onKey);
  overlay.remove();
}

function heading(text) {
  const node = document.createElement("div");
  node.textContent = text;
  node.style.cssText = "font-weight:600";
  return node;
}

function label(text) {
  const node = document.createElement("label");
  node.textContent = text;
  node.style.cssText = "font-size:12px;opacity:0.8";
  return node;
}

function message(text) {
  const node = document.createElement("div");
  node.className = "qm-job-status";
  node.textContent = text;
  node.style.cssText = "min-height:1.2em;font-size:13px";
  return node;
}

function closeButton() {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Close";
  button.style.cssText = buttonStyle("transparent");
  button.addEventListener("click", closeEditor);
  return button;
}

function fieldStyle() {
  return [
    "width:100%",
    "box-sizing:border-box",
    "background:#111",
    "color:inherit",
    "border:1px solid rgba(255,255,255,0.2)",
    "border-radius:6px",
    "padding:8px",
    "font:inherit",
  ].join(";");
}

function buttonStyle(background) {
  return [
    "background:" + background,
    "color:inherit",
    "border:1px solid rgba(255,255,255,0.25)",
    "border-radius:6px",
    "padding:6px 12px",
    "cursor:pointer",
  ].join(";");
}
