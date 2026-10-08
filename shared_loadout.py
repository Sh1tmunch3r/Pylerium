"""Shared state API available to every script launched by the orchestrator.

    from shared_loadout import get, set_value, update
    update('processed_count', lambda old: (old or 0) + 1)

Updates hold a SQLite write transaction so concurrent operators cannot lose increments.
"""
import json
import os
import sqlite3
from contextlib import contextmanager


@contextmanager
def connection():
    path = os.environ.get('ORCHESTRATOR_SHARED_DB')
    if not path:
        raise RuntimeError('Run this script from the orchestration menu to use shared state')
    db = sqlite3.connect(path, timeout=30)
    try:
        yield db
    finally:
        db.close()


def get(key, default=None):
    with connection() as db:
        row = db.execute('SELECT value FROM shared WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default


def set_value(key, value):
    with connection() as db, db:
        db.execute('INSERT OR REPLACE INTO shared VALUES (?,?)', (key, json.dumps(value)))
    return value


def update(key, function, default=None):
    with connection() as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM shared WHERE key=?', (key,)).fetchone()
        value = function(json.loads(row[0]) if row else default)
        db.execute('INSERT OR REPLACE INTO shared VALUES (?,?)', (key, json.dumps(value)))
    return value


def all_values():
    with connection() as db:
        return {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM shared ORDER BY key')}
