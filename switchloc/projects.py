"""SQLite project storage with atomic revision snapshots and input provenance."""
import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def file_info(path):
    p = Path(path)
    digest = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): digest.update(chunk)
    return {'path': str(p.resolve()), 'sha256': digest.hexdigest(), 'size': p.stat().st_size}


def save_project(path, name, data, inputs=(), previous_sources=()):
    """Append a revision in one transaction; do not modify the input files."""
    path = Path(path)
    if not name.strip(): raise ValueError('نام پروژه لازم است')
    sources_by_path = {s['path']: s for s in previous_sources}
    for p in inputs:
        info = file_info(p); sources_by_path[info['path']] = info
    sources = list(sources_by_path.values())
    if any(Path(s['path']) == path.resolve() for s in sources):
        raise ValueError('فایل پروژه نباید همان فایل ورودی باشد')
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False)
    provenance = json.dumps(sources, ensure_ascii=False)
    exists = path.exists()
    if exists:
        # Never initialise or modify an unrelated SQLite database.
        try:
            with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as check:
                row = check.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                if not row or row[0] != str(SCHEMA_VERSION): raise ValueError('فایل پروژه معتبر نیست')
        except sqlite3.Error as exc: raise ValueError('فایل پروژه معتبر نیست') from exc
    with sqlite3.connect(str(path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, name TEXT NOT NULL, data TEXT NOT NULL, sources TEXT NOT NULL)')
        row = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if row and row[0] != str(SCHEMA_VERSION): raise ValueError('نسخه پروژه پشتیبانی نمی‌شود')
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        db.execute('INSERT INTO revisions(name,data,sources) VALUES(?,?,?)', (name.strip(), payload, provenance))


def load_project(path):
    """Open existing DB read-only and load the latest snapshot."""
    path = Path(path).resolve()
    if not path.is_file(): raise ValueError('فایل پروژه یافت نشد')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if not row or row[0] != str(SCHEMA_VERSION): raise ValueError('نسخه پروژه پشتیبانی نمی‌شود')
        revision = db.execute('SELECT id,created_at,name,data,sources FROM revisions ORDER BY id DESC LIMIT 1').fetchone()
        if not revision: raise ValueError('پروژه فاقد نسخه ذخیره‌شده است')
        id_, created, name, data, sources = revision
        return {'revision': id_, 'created_at': created, 'name': name,
                'data': json.loads(data), 'sources': json.loads(sources)}
