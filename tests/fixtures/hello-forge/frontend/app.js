const db = new DataClient();
db.namespace = "hello-forge";

document.getElementById("greet-btn").addEventListener("click", async () => {
  const name = document.getElementById("name-input").value;
  const resp = await fetch(`/hello/api/greet?name=${encodeURIComponent(name)}`);
  const data = await resp.json();
  document.getElementById("greet-result").textContent = JSON.stringify(data, null, 2);
});

document.getElementById("save-btn").addEventListener("click", async () => {
  const text = document.getElementById("note-input").value;
  if (!text) return;
  await db.create("notes", { text, ts: new Date().toISOString() });
  document.getElementById("note-input").value = "";
  loadNotes();
});

document.getElementById("about-btn").addEventListener("click", () => {
  document.getElementById("about-modal").open();
});

async function loadNotes() {
  const notes = await db.list("notes");
  const el = document.getElementById("notes-list");
  el.innerHTML = notes.map(n =>
    `<div class="forge-card" style="margin:.5rem 0">
      <small style="color:#6b7280">${n.data.ts || ''}</small>
      <p>${n.data.text}</p>
    </div>`
  ).join("");
}
loadNotes();
