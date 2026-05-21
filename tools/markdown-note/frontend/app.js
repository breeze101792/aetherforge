const API = '/md/api';

// DOM elements
const storageList = document.getElementById('storage-list');
const fileTree = document.getElementById('file-tree');
const editor = document.getElementById('editor');
const preview = document.getElementById('preview');
const currentFile = document.getElementById('current-file');
const reloadBtn = document.getElementById('reload-btn');
const toggleEditBtn = document.getElementById('toggle-edit-btn');
const editorPane = document.getElementById('editor-pane');
const editorPreview = document.getElementById('editor-preview');
const closeEditorBtn = document.getElementById('close-editor-btn');
const toast = document.getElementById('toast');
const storageModal = document.getElementById('storage-modal');
const newItemModal = document.getElementById('new-item-modal');

// State
let storages = [];
let activeStorage = null;
let currentDir = null;       // {name, path} — the directory being browsed
let openFilePath = null;     // full "root:rel/path" string
let openFileName = null;
let lastMtime = null;
let treeCache = {};          // path -> [{name, type, path}]

// ── Toast ──
function showToast(msg) {
  toast.textContent = msg;
  toast.style.display = 'block';
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => { toast.style.display = 'none'; }, 2000);
}

// ── Storage management ──
async function loadStorages() {
  const resp = await fetch(`${API}/storages`);
  storages = await resp.json();
  renderStorageList();
  if (activeStorage) {
    const found = storages.find(s => s.data.name === activeStorage);
    if (!found) {
      activeStorage = null;
      currentDir = null;
      fileTree.innerHTML = '';
      closeFile();
    }
  }
}

function renderStorageList() {
  storageList.innerHTML = storages.map(s => `
    <div class="mdl-storage-item${s.data.name === activeStorage ? ' active' : ''}" data-storage="${escAttr(s.data.name)}">
      <div>
        <span>${escHtml(s.data.name)}</span>
        <span class="path-hint">${escHtml(s.data.path)}</span>
      </div>
      <button class="icon-btn" data-action="remove-storage" data-id="${s.id}" data-name="${escAttr(s.data.name)}" title="Remove">&times;</button>
    </div>
  `).join('');

  storageList.querySelectorAll('.mdl-storage-item').forEach(el => {
    el.addEventListener('click', (e) => {
      if (e.target.dataset.action === 'remove-storage') return;
      selectStorage(el.dataset.storage);
    });
  });
  storageList.querySelectorAll('[data-action="remove-storage"]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await fetch(`${API}/storages/${btn.dataset.id}`, { method: 'DELETE' });
      if (btn.dataset.name === activeStorage) {
        activeStorage = null; currentDir = null; fileTree.innerHTML = ''; closeFile();
      }
      showToast('Storage removed');
      await loadStorages();
    });
  });
}

async function selectStorage(name) {
  activeStorage = name;
  currentDir = { name, path: `${name}:` };
  renderStorageList();
  document.getElementById('new-file-btn').disabled = false;
  document.getElementById('new-dir-btn').disabled = false;
  await loadDirectory(currentDir.path);
}

// ── File tree ──
async function loadDirectory(path) {
  const resp = await fetch(`${API}/files?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    fileTree.innerHTML = '<div style="padding:1rem;color:#9ca3af;">Unable to read directory</div>';
    return;
  }
  const items = await resp.json();
  treeCache[path] = items;
  renderTree(path);
}

function renderTree(path) {
  const rootPath = `${activeStorage}:`;
  const rootItems = treeCache[rootPath] || [];
  fileTree.innerHTML = buildTreeHtml(rootPath, rootItems, 0);
  bindTreeClicks();
}

function buildTreeHtml(parentPath, items, depth) {
  if (!items || items.length === 0) {
    if (depth === 0) return '<div style="padding:.5rem 1rem;color:#9ca3af;font-size:.8rem;">Empty</div>';
    return '';
  }
  const dirs = items.filter(i => i.type === 'dir');
  const files = items.filter(i => i.type === 'file');
  const sorted = [...dirs, ...files];

  return sorted.map(item => {
    const isDir = item.type === 'dir';
    const icon = isDir ? '&#128193;' : '&#128196;';
    const cssClass = isDir ? 'mdl-tree-dir' : '';
    const isOpen = openFilePath === item.path;
    const hasChildren = isDir && treeCache[item.path] && treeCache[item.path].length > 0;
    const collapsed = isDir && !hasChildren;

    let childrenHtml = '';
    if (isDir && treeCache[item.path]) {
      childrenHtml = `<div class="mdl-tree-children">${buildTreeHtml(item.path, treeCache[item.path], depth + 1)}</div>`;
    }

    return `
      <div class="mdl-tree-item ${cssClass}${isOpen ? ' active' : ''}" data-path="${escAttr(item.path)}" data-type="${item.type}">
        <span class="tree-icon">${icon}</span>
        <span>${escHtml(item.name)}</span>
      </div>
      ${childrenHtml}
    `;
  }).join('');
}

function bindTreeClicks() {
  fileTree.querySelectorAll('.mdl-tree-item').forEach(el => {
    el.addEventListener('click', async (e) => {
      const path = el.dataset.path;
      const type = el.dataset.type;
      if (type === 'dir') {
        if (!treeCache[path]) await loadDirectory(path);
        const children = el.nextElementSibling;
        if (children && children.classList.contains('mdl-tree-children')) {
          children.classList.toggle('collapsed');
        }
      } else {
        await openFile(path);
      }
    });
  });
}

// ── Edit mode toggle ──
function enterEditMode() {
  editorPreview.classList.add('editing');
  toggleEditBtn.textContent = 'Preview';
  editor.focus();
}

function exitEditMode() {
  editorPreview.classList.remove('editing');
  toggleEditBtn.textContent = 'Edit';
}

toggleEditBtn.addEventListener('click', () => {
  if (!openFilePath) return;
  if (editorPreview.classList.contains('editing')) {
    exitEditMode();
  } else {
    enterEditMode();
  }
});

closeEditorBtn.addEventListener('click', exitEditMode);

// ── File operations ──
async function openFile(path) {
  const resp = await fetch(`${API}/file?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    showToast('Failed to open file');
    return;
  }
  const data = await resp.json();
  openFilePath = path;
  openFileName = data.name;
  editor.value = data.content;
  editor.disabled = false;
  reloadBtn.disabled = false;
  toggleEditBtn.disabled = false;
  currentFile.textContent = path;
  lastMtime = data.mtime;
  dirty = false;
  exitEditMode();
  await renderPreview();
  if (treeCache[`${activeStorage}:`]) renderTree(`${activeStorage}:`);
}

function closeFile() {
  openFilePath = null;
  openFileName = null;
  editor.value = '';
  editor.disabled = true;
  reloadBtn.disabled = true;
  toggleEditBtn.disabled = true;
  currentFile.textContent = 'No file open';
  preview.innerHTML = '';
  exitEditMode();
}

let dirty = false;

async function saveFile() {
  if (!openFilePath) return;
  const resp = await fetch(`${API}/file?path=${encodeURIComponent(openFilePath)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: editor.value }),
  });
  const result = await resp.json();
  lastMtime = result.mtime;
  dirty = false;
  await renderPreview();
}

async function renderPreview() {
  const md = editor.value;
  if (!md.trim()) { preview.innerHTML = ''; return; }
  const resp = await fetch(`${API}/render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown: md }),
  });
  const data = await resp.json();
  preview.innerHTML = data.html;
}

// Debounced preview + autosave
let renderTimer = null;
let autosaveTimer = null;
editor.addEventListener('input', () => {
  dirty = true;
  clearTimeout(renderTimer);
  renderTimer = setTimeout(renderPreview, 300);
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(() => {
    if (dirty && openFilePath) saveFile();
  }, 1500);
});

// ── Edit toolbar ──
const tbActions = {
  bold:         { wrap: '**', placeholder: 'bold text' },
  italic:       { wrap: '*', placeholder: 'italic text' },
  strikethrough:{ wrap: '~~', placeholder: 'strikethrough text' },
  h1:           { prefix: '# ', placeholder: 'Heading 1' },
  h2:           { prefix: '## ', placeholder: 'Heading 2' },
  h3:           { prefix: '### ', placeholder: 'Heading 3' },
  code:         { wrap: '`', placeholder: 'code' },
  codeblock:    { block: true, prefix: '```\n', suffix: '\n```', placeholder: 'code here' },
  link:         { wrap: ['[', '](url)'], placeholder: 'link text' },
  image:        { wrap: ['![', '](url)'], placeholder: 'alt text' },
  ul:           { prefix: '- ', placeholder: 'List item' },
  ol:           { prefix: '1. ', placeholder: 'List item' },
  quote:        { prefix: '> ', placeholder: 'Blockquote' },
  table:        { block: true, prefix: '| Col A | Col B | Col C |\n|-------|-------|-------|\n| ', suffix: ' |\n', placeholder: 'Cell A1 | Cell B1 | Cell C1\n| Cell A2 | Cell B2 | Cell C2' },
  hr:           { block: true, prefix: '\n---\n', placeholder: '' },
};

document.getElementById('edit-toolbar').addEventListener('click', (e) => {
  const btn = e.target.closest('.mdl-tb-btn');
  if (!btn || editor.disabled) return;
  const action = btn.dataset.action;
  if (action && tbActions[action]) insertMarkdown(action);
});

function insertMarkdown(action) {
  const cfg = tbActions[action];
  const ta = editor;
  const start = ta.selectionStart;
  const end = ta.selectionEnd;
  const sel = ta.value.substring(start, end);

  let replacement, cursorOffset;
  if (sel) {
    if (cfg.wrap) {
      if (Array.isArray(cfg.wrap)) {
        replacement = cfg.wrap[0] + sel + cfg.wrap[1];
        cursorOffset = replacement.length;
      } else {
        replacement = cfg.wrap + sel + cfg.wrap;
        cursorOffset = replacement.length;
      }
    } else if (cfg.prefix) {
      const lines = sel.split('\n');
      replacement = lines.map(l => cfg.prefix + l).join('\n');
      if (cfg.suffix) replacement += cfg.suffix;
      cursorOffset = replacement.length;
    }
  } else {
    if (cfg.block) {
      replacement = cfg.prefix + cfg.placeholder + cfg.suffix;
      cursorOffset = cfg.prefix.length + cfg.placeholder.length;
    } else if (cfg.wrap) {
      replacement = Array.isArray(cfg.wrap)
        ? cfg.wrap[0] + cfg.placeholder + cfg.wrap[1]
        : cfg.wrap + cfg.placeholder + cfg.wrap;
      cursorOffset = replacement.length;
      // Place cursor inside the wrap, before the closing marker
      const closing = Array.isArray(cfg.wrap) ? cfg.wrap[1] : cfg.wrap;
      if (closing) cursorOffset -= closing.length;
    } else if (cfg.prefix) {
      replacement = cfg.prefix + cfg.placeholder;
      cursorOffset = replacement.length;
    }
  }

  if (replacement != null) {
    ta.value = ta.value.substring(0, start) + replacement + ta.value.substring(end);
    const newPos = start + cursorOffset;
    ta.selectionStart = ta.selectionEnd = newPos;
    ta.focus();
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

// Keyboard shortcuts for formatting
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'b' && !editor.disabled) {
    e.preventDefault();
    insertMarkdown('bold');
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'i' && !editor.disabled) {
    e.preventDefault();
    insertMarkdown('italic');
  }
});

// ── Add storage ──
document.getElementById('add-storage-btn').addEventListener('click', () => {
  document.getElementById('storage-name').value = '';
  document.getElementById('storage-path').value = '';
  storageModal.open();
});

document.getElementById('storage-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('storage-name').value.trim();
  const path = document.getElementById('storage-path').value.trim();
  const resp = await fetch(`${API}/storages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, path }),
  });
  if (!resp.ok) {
    const err = await resp.json();
    showToast(err.detail || 'Failed to add storage');
    return;
  }
  storageModal.close();
  showToast('Storage added');
  await loadStorages();
});

// ── New file / folder ──
document.getElementById('new-file-btn').addEventListener('click', () => {
  document.getElementById('new-item-title').textContent = 'New File';
  document.getElementById('new-item-type').value = 'file';
  document.getElementById('new-item-name').value = '';
  newItemModal.open();
});

document.getElementById('new-dir-btn').addEventListener('click', () => {
  document.getElementById('new-item-title').textContent = 'New Folder';
  document.getElementById('new-item-type').value = 'dir';
  document.getElementById('new-item-name').value = '';
  newItemModal.open();
});

document.getElementById('new-item-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const type = document.getElementById('new-item-type').value;
  const name = document.getElementById('new-item-name').value.trim();
  if (!currentDir) return;

  const basePath = currentDir.path;
  const relPart = basePath.includes(':') ? basePath.split(':')[1] || '' : '';
  const itemPath = relPart ? `${activeStorage}:${relPart}/${name}` : `${activeStorage}:${name}`;

  if (type === 'dir') {
    await fetch(`${API}/mkdir?path=${encodeURIComponent(itemPath)}`, { method: 'POST' });
  } else {
    await fetch(`${API}/file?path=${encodeURIComponent(itemPath)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: '' }),
    });
  }
  newItemModal.close();
  showToast(type === 'dir' ? 'Folder created' : 'File created');
  treeCache = {};
  await loadDirectory(currentDir.path);
});

// ── Reload ──
reloadBtn.addEventListener('click', async () => {
  if (!openFilePath) return;
  const resp = await fetch(`${API}/file?path=${encodeURIComponent(openFilePath)}`);
  if (!resp.ok) { showToast('Failed to reload'); return; }
  const data = await resp.json();
  editor.value = data.content;
  lastMtime = data.mtime;
  dirty = false;
  showToast('Reloaded');
  await renderPreview();
});

// ── Delete file ──
reloadBtn.addEventListener('contextmenu', async (e) => {
  e.preventDefault();
  if (!openFilePath) return;
  if (!confirm(`Delete ${openFileName}?`)) return;
  await fetch(`${API}/file?path=${encodeURIComponent(openFilePath)}`, { method: 'DELETE' });
  showToast('File deleted');
  treeCache = {};
  closeFile();
  if (currentDir) await loadDirectory(currentDir.path);
});

// ── Detect external changes ──
window.addEventListener('focus', async () => {
  if (!openFilePath || !lastMtime) return;
  try {
    const resp = await fetch(`${API}/file/mtime?path=${encodeURIComponent(openFilePath)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.mtime !== lastMtime) {
      showToast('File changed on disk — click Reload to update');
    }
  } catch (_) { /* ignore network errors during focus check */ }
});

// ── Helpers ──
function escHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function escAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Init ──
loadStorages();
