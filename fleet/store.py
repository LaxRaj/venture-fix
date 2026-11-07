"""SQLite state: ventures, tasks, artifacts, prospects, approvals, messages, ledger, usage."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SCHEMA = """
create table if not exists ventures(id text primary key, data text, status text default 'active', payment_link text default '');
create table if not exists tasks(id integer primary key autoincrement, venture_id text, kind text, title text, brief text,
  depends text default '[]', status text default 'pending', tier integer default 0, attempts integer default 0,
  note text default '', ord integer default 0, updated real);
create table if not exists artifacts(id integer primary key autoincrement, task_id integer, venture_id text, kind text, body text, tier integer, ts real);
create table if not exists attempts(id integer primary key autoincrement, task_id integer, venture_id text, tier integer, model text, ok integer, issues text, tokens_in integer, tokens_out integer, ts real);
create table if not exists prospects(id integer primary key autoincrement, venture_id text, name text, company text, email text, note text default '', status text default 'new', unique(venture_id, email));
create table if not exists approvals(id integer primary key autoincrement, venture_id text, prospect_id integer, kind text, subject text, body text, status text default 'pending', ts real);
create table if not exists messages(id integer primary key autoincrement, venture_id text, prospect_id integer, direction text, body text, ts real);
create table if not exists ledger(id integer primary key autoincrement, venture_id text, cents integer, source text, ref text unique, note text, ts real);
create table if not exists settings(k text primary key, v text);
create table if not exists events(id integer primary key autoincrement, venture_id text, msg text, ts real);
"""


class Store:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript(SCHEMA)

    def q(self, sql: str, args: Iterable = ()) -> List[Dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, tuple(args)).fetchall()]

    def one(self, sql: str, args: Iterable = ()) -> Optional[Dict]:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def x(self, sql: str, args: Iterable = ()) -> int:
        with self.lock:
            cur = self.db.execute(sql, tuple(args))
            self.db.commit()
            return cur.lastrowid or 0

    # settings / events ------------------------------------------------
    def setting(self, k: str, default: str = "") -> str:
        r = self.one("select v from settings where k=?", (k,))
        return r["v"] if r else default

    def set_setting(self, k: str, v: str) -> None:
        self.x("insert into settings(k,v) values(?,?) on conflict(k) do update set v=excluded.v", (k, v))

    def log(self, venture_id: str, msg: str) -> None:
        self.x("insert into events(venture_id,msg,ts) values(?,?,?)", (venture_id, msg, time.time()))

    # ventures ---------------------------------------------------------
    def seed_ventures(self, rows: List[dict]) -> int:
        n = 0
        for r in rows:
            if not self.one("select id from ventures where id=?", (r["id"],)):
                self.x("insert into ventures(id,data) values(?,?)", (r["id"], json.dumps(r)))
                n += 1
        return n

    def venture(self, vid: str) -> Optional[Dict]:
        r = self.one("select * from ventures where id=?", (vid,))
        if r:
            r["data"] = json.loads(r["data"])
        return r

    def tokens_today(self) -> int:
        since = time.time() - 86400
        r = self.one("select coalesce(sum(tokens_in+tokens_out),0) n from attempts where ts>?", (since,))
        return int(r["n"]) if r else 0
