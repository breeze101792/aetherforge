import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from shared.backend.data_client import DataClient


def create_app():
    app = FastAPI()
    db = DataClient()

    def _storages():
        return {s["data"]["name"]: s["data"]["path"] for s in db.list("storages", limit=100)}

    def _resolve_root(path_str: str) -> tuple[str, str]:
        """Resolve 'root_name:relative/path' to (resolved_abs_path, root_name).
        Raises 403 if the resolved path escapes the root."""
        if ":" not in path_str:
            raise HTTPException(400, "Path must be 'root_name:relative/path' format")
        root_name, rel = path_str.split(":", 1)
        storages = _storages()
        if root_name not in storages:
            raise HTTPException(404, f"Storage '{root_name}' not found")
        root = storages[root_name]
        resolved = os.path.normpath(os.path.join(root, rel))
        root_real = os.path.realpath(root)
        resolved_real = os.path.realpath(resolved)
        if not resolved_real.startswith(root_real + os.sep) and resolved_real != root_real:
            raise HTTPException(403, "Path escapes storage root")
        return resolved, root_name

    def _safe_ext(filename: str) -> bool:
        """Only allow .md, .mdx, .markdown, .txt files."""
        return filename.lower().endswith((".md", ".mdx", ".markdown", ".txt"))

    # ── Storage management ──

    @app.get("/storages")
    def list_storages():
        return db.list("storages", limit=100)

    @app.post("/storages")
    async def add_storage(request: Request):
        body = await request.json()
        name = body.get("name", "").strip()
        path = body.get("path", "").strip()
        if not name or not path:
            raise HTTPException(400, "name and path required")
        if not os.path.isdir(path):
            raise HTTPException(400, f"Directory not found: {path}")
        # Check for duplicate name
        for s in db.list("storages", limit=100):
            if s["data"]["name"] == name:
                return db.update("storages", s["id"], {"name": name, "path": path})
        return db.create("storages", {"name": name, "path": path})

    @app.delete("/storages/{storage_id}")
    def remove_storage(storage_id: int):
        return db.delete("storages", storage_id)

    # ── File operations ──

    @app.get("/files")
    def list_files(path: str = ""):
        """List files and directories at 'root_name:relative/path'."""
        if path and ":" in path:
            abs_path, root_name = _resolve_root(path)
        else:
            # List all storages at top level
            result = []
            for name, root_path in _storages().items():
                result.append({"name": name, "type": "storage", "path": f"{name}:"})
            return result

        if not os.path.exists(abs_path):
            raise HTTPException(404, "Path not found")

        items = []
        if os.path.isdir(abs_path):
            try:
                entries = sorted(os.listdir(abs_path), key=lambda x: (not os.path.isdir(os.path.join(abs_path, x)), x.lower()))
            except PermissionError:
                raise HTTPException(403, "Permission denied")
            for entry in entries:
                entry_path = os.path.join(abs_path, entry)
                is_dir = os.path.isdir(entry_path)
                if is_dir and entry.startswith("."):
                    continue
                if not is_dir and not _safe_ext(entry):
                    continue
                rel_part = path.split(":", 1)[1] if ":" in path else ""
                items.append({
                    "name": entry,
                    "type": "dir" if is_dir else "file",
                    "path": f"{root_name}:{os.path.join(rel_part, entry)}",
                })
        return items

    @app.get("/file")
    def read_file(path: str = ""):
        if not path:
            raise HTTPException(400, "path required")
        abs_path, _ = _resolve_root(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(404, "File not found")
        if not _safe_ext(os.path.basename(abs_path)):
            raise HTTPException(400, "Unsupported file type")
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"path": path, "content": content, "name": os.path.basename(abs_path), "mtime": os.path.getmtime(abs_path)}

    @app.post("/file")
    async def write_file(request: Request, path: str = ""):
        if not path:
            raise HTTPException(400, "path required")
        abs_path, _ = _resolve_root(path)
        if not _safe_ext(os.path.basename(abs_path)):
            raise HTTPException(400, "Unsupported file type")
        body = await request.json()
        content = body.get("content", "")
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"saved": True, "path": path, "mtime": os.path.getmtime(abs_path)}

    @app.get("/file/mtime")
    def file_mtime(path: str = ""):
        if not path:
            raise HTTPException(400, "path required")
        abs_path, _ = _resolve_root(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(404, "File not found")
        return {"mtime": os.path.getmtime(abs_path)}

    @app.delete("/file")
    def delete_file(path: str = ""):
        if not path:
            raise HTTPException(400, "path required")
        abs_path, _ = _resolve_root(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(404, "File not found")
        os.remove(abs_path)
        return {"deleted": True}

    @app.post("/mkdir")
    async def create_dir(request: Request, path: str = ""):
        if not path:
            raise HTTPException(400, "path required")
        abs_path, _ = _resolve_root(path)
        os.makedirs(abs_path, exist_ok=True)
        return {"created": True}

    # ── Markdown rendering ──

    @app.post("/render")
    async def render_markdown(request: Request):
        """Server-side GFM-to-HTML rendering."""
        body = await request.json()
        md_text = body.get("markdown", "")
        html = _render_md(md_text)
        return {"html": html}

    return app


# ── Minimal GFM renderer ──

def _render_md(text: str) -> str:
    """Convert markdown to HTML. Supports headings, bold, italic, code,
    fenced code blocks, links, images, lists, blockquotes, tables, hr."""
    # Escape HTML first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Fenced code blocks (must come before inline code)
    def _fence(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return f'<pre><code class="language-{lang}">{code}</code></pre>'
    text = re.sub(r'```(\w*)\n(.*?)```', _fence, text, flags=re.DOTALL)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Bold and italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'___(.+?)___', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    text = re.sub(r'_(.+?)_', r'<em>\1</em>', text)

    # Images (before links)
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img alt="\1" src="\2">', text)

    # Links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Headings
    text = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

    # Horizontal rule
    text = re.sub(r'^(---|\*\*\*|___)\s*$', r'<hr>', text, flags=re.MULTILINE)

    # Blockquotes
    text = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
    # Merge adjacent blockquotes
    text = re.sub(r'</blockquote>\n<blockquote>', r'\n', text)

    # Unordered lists
    text = re.sub(r'^[\*\-] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\n\g<0></ul>', text)
    # Numbered lists
    text = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)

    # Tables
    lines = text.split('\n')
    result = []
    in_table = False
    for i, line in enumerate(lines):
        if '|' in line and line.strip().startswith('|'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if all(c.replace('-', '').replace(':', '').replace(' ', '') == '' for c in cells):
                continue  # separator row
            tag = 'th' if not in_table else 'td'
            row = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
            if not in_table:
                result.append('<table>')
                in_table = True
            result.append(f'<tr>{row}</tr>')
        else:
            if in_table:
                result.append('</table>')
                in_table = False
            result.append(line)
    if in_table:
        result.append('</table>')
    text = '\n'.join(result)

    # Paragraphs: wrap remaining lines in <p>, skipping block-level HTML
    _block_tags = {'pre', 'table', 'tr', 'th', 'td', 'thead', 'tbody',
                   'ul', 'ol', 'li', 'blockquote', 'hr', 'h1', 'h2', 'h3', 'h4'}
    out = []
    in_block = False
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped:
            out.append('')
            continue
        # Check if this line is a self-contained HTML element
        if re.match(r'^<(\w+).*>.*</\1>$|^<(\w+)[^>]*/?>$', stripped):
            out.append(stripped)
            continue
        # Check if this line opens or is part of a block element
        tag_match = re.match(r'^</?(\w+)', stripped)
        if tag_match and tag_match.group(1) in _block_tags:
            out.append(stripped)
            in_block = True
            if stripped.startswith('</'):
                in_block = False
            continue
        if in_block:
            out.append(stripped)
            if stripped.startswith('</'):
                in_block = False
            continue
        out.append(f'<p>{stripped}</p>')
    return '\n'.join(out)
