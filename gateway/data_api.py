import json
import os
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/_api/data")

RESERVED = {"_api", "_health", "_tool", "shared"}


def get_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _table_name(tool_name: str, resource: str) -> str:
    # Sanitize: only allow alphanumeric, underscore, hyphen
    safe_tool = "".join(c for c in tool_name if c.isalnum() or c in "_-")
    safe_res = "".join(c for c in resource if c.isalnum() or c in "_-")
    return f"t_{safe_tool}_{safe_res}"


def _ensure_table(conn: sqlite3.Connection, table: str):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _validate_name(name: str):
    if not name or "/" in name or ".." in name or "\\" in name:
        raise HTTPException(400, "invalid name")


def _row_to_dict(row) -> dict:
    d = dict(row)
    try:
        d["data"] = json.loads(d["data"])
    except (json.JSONDecodeError, TypeError):
        pass
    return d


@router.post("/{tool_name}/{resource}")
async def create_record(tool_name: str, resource: str, request: Request):
    _validate_name(tool_name)
    _validate_name(resource)
    body = await request.json()
    conn = get_db(request.app.state.db_path)
    table = _table_name(tool_name, resource)
    _ensure_table(conn, table)
    cur = conn.execute(f'INSERT INTO "{table}" (data) VALUES (?)', (json.dumps(body),))
    conn.commit()
    row = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (cur.lastrowid,)).fetchone()
    return JSONResponse(_row_to_dict(row), status_code=201)


@router.get("/{tool_name}/{resource}")
async def list_records(tool_name: str, resource: str, request: Request,
                       limit: int = 100, offset: int = 0):
    _validate_name(tool_name)
    _validate_name(resource)
    conn = get_db(request.app.state.db_path)
    table = _table_name(tool_name, resource)
    _ensure_table(conn, table)
    rows = conn.execute(
        f'SELECT * FROM "{table}" ORDER BY id DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{tool_name}/{resource}/{record_id}")
async def get_record(tool_name: str, resource: str, record_id: int, request: Request):
    _validate_name(tool_name)
    _validate_name(resource)
    conn = get_db(request.app.state.db_path)
    table = _table_name(tool_name, resource)
    _ensure_table(conn, table)
    row = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (record_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "record not found")
    return _row_to_dict(row)


@router.put("/{tool_name}/{resource}/{record_id}")
async def update_record(tool_name: str, resource: str, record_id: int, request: Request):
    _validate_name(tool_name)
    _validate_name(resource)
    body = await request.json()
    conn = get_db(request.app.state.db_path)
    table = _table_name(tool_name, resource)
    _ensure_table(conn, table)
    conn.execute(
        f'UPDATE "{table}" SET data = ?, updated_at = datetime("now") WHERE id = ?',
        (json.dumps(body), record_id)
    )
    conn.commit()
    row = conn.execute(f'SELECT * FROM "{table}" WHERE id = ?', (record_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "record not found")
    return _row_to_dict(row)


@router.delete("/{tool_name}/{resource}/{record_id}")
async def delete_record(tool_name: str, resource: str, record_id: int, request: Request):
    _validate_name(tool_name)
    _validate_name(resource)
    conn = get_db(request.app.state.db_path)
    table = _table_name(tool_name, resource)
    _ensure_table(conn, table)
    conn.execute(f'DELETE FROM "{table}" WHERE id = ?', (record_id,))
    conn.commit()
    return {"deleted": True}
