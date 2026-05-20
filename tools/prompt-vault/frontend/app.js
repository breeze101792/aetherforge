const db = new DataClient();
db.namespace = "prompt-vault";

const list = document.getElementById("prompt-list");
const empty = document.getElementById("empty-state");
const search = document.getElementById("search-input");
const toast = document.getElementById("toast");
const editorModal = document.getElementById("editor-modal");
const viewModal = document.getElementById("view-modal");

let allPrompts = [];

search.addEventListener("input", () => render(allPrompts));

document.getElementById("add-btn").addEventListener("click", () => {
  document.getElementById("editor-title").textContent = "New Prompt";
  document.getElementById("edit-id").value = "";
  document.getElementById("title-input").value = "";
  document.getElementById("tags-input").value = "";
  document.getElementById("content-input").value = "";
  editorModal.open();
});

document.getElementById("cancel-btn").addEventListener("click", () => editorModal.close());

document.getElementById("editor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("edit-id").value;
  const payload = {
    title: document.getElementById("title-input").value,
    tags: document.getElementById("tags-input").value,
    content: document.getElementById("content-input").value,
  };
  if (id) payload.id = parseInt(id);
  await fetch(`/prompts/api/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  editorModal.close();
  showToast(id ? "Prompt updated" : "Prompt saved");
  await load();
});

document.getElementById("copy-btn").addEventListener("click", () => {
  const text = document.getElementById("view-body").textContent;
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard"));
});

document.getElementById("edit-from-view-btn").addEventListener("click", () => {
  const id = viewModal.dataset.promptId;
  const p = allPrompts.find(x => x.id === parseInt(id));
  if (!p) return;
  viewModal.close();
  document.getElementById("editor-title").textContent = "Edit Prompt";
  document.getElementById("edit-id").value = p.id;
  document.getElementById("title-input").value = p.data.title || "";
  document.getElementById("tags-input").value = p.data.tags || "";
  document.getElementById("content-input").value = p.data.content || "";
  editorModal.open();
});

function showToast(msg) {
  toast.textContent = msg;
  toast.style.display = "block";
  setTimeout(() => { toast.style.display = "none"; }, 2000);
}

function render(items) {
  const q = search.value.toLowerCase();
  const filtered = q
    ? items.filter(p =>
        (p.data.title || "").toLowerCase().includes(q) ||
        (p.data.content || "").toLowerCase().includes(q) ||
        (p.data.tags || "").toLowerCase().includes(q))
    : items;

  if (filtered.length === 0) {
    list.innerHTML = "";
    empty.style.display = items.length === 0 ? "block" : "none";
    if (items.length > 0) {
      empty.innerHTML = "<p>No prompts match your search.</p>";
    }
    return;
  }
  empty.style.display = "none";

  list.innerHTML = filtered.map(p => {
    const tags = (p.data.tags || "").split(",").filter(Boolean).map(t => t.trim());
    const preview = (p.data.content || "").substring(0, 120);
    return `
      <div class="forge-card prompt-card" data-id="${p.id}">
        <div class="card-header">
          <h3 class="card-title">${esc(p.data.title || "Untitled")}</h3>
          <div class="card-actions">
            <button class="icon-btn view-btn" data-id="${p.id}" title="View">&#9654;</button>
            <button class="icon-btn edit-btn" data-id="${p.id}" title="Edit">&#9998;</button>
            <button class="icon-btn delete-btn" data-id="${p.id}" title="Delete">&#10005;</button>
          </div>
        </div>
        ${tags.length ? `<div class="tags-row">${tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
        <p class="card-preview">${esc(preview)}${p.data.content && p.data.content.length > 120 ? "..." : ""}</p>
      </div>`;
  }).join("");

  list.querySelectorAll(".view-btn").forEach(b => b.addEventListener("click", () => viewPrompt(b.dataset.id)));
  list.querySelectorAll(".edit-btn").forEach(b => b.addEventListener("click", () => editPrompt(b.dataset.id)));
  list.querySelectorAll(".delete-btn").forEach(b => b.addEventListener("click", () => deletePrompt(b.dataset.id)));
}

function viewPrompt(id) {
  const p = allPrompts.find(x => x.id === parseInt(id));
  if (!p) return;
  viewModal.dataset.promptId = id;
  document.getElementById("view-title").textContent = p.data.title || "Untitled";
  document.getElementById("view-body").textContent = p.data.content || "";
  const tags = (p.data.tags || "").split(",").filter(Boolean).map(t => t.trim());
  document.getElementById("view-tags").innerHTML = tags.length
    ? tags.map(t => `<span class="tag">${esc(t)}</span>`).join("")
    : "";
  viewModal.open();
}

function editPrompt(id) {
  const p = allPrompts.find(x => x.id === parseInt(id));
  if (!p) return;
  document.getElementById("editor-title").textContent = "Edit Prompt";
  document.getElementById("edit-id").value = p.id;
  document.getElementById("title-input").value = p.data.title || "";
  document.getElementById("tags-input").value = p.data.tags || "";
  document.getElementById("content-input").value = p.data.content || "";
  editorModal.open();
}

async function deletePrompt(id) {
  await fetch(`/prompts/api/delete/${id}`, { method: "DELETE" });
  showToast("Prompt deleted");
  await load();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

async function load() {
  const resp = await fetch("/prompts/api/list");
  allPrompts = await resp.json();
  render(allPrompts);
  if (allPrompts.length === 0) {
    empty.style.display = "block";
    empty.innerHTML = "<p>No prompts saved yet.</p><p>Click <strong>+ New Prompt</strong> to get started.</p>";
  }
}

load();
