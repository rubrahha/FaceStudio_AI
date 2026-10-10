"""Consent-only on-device SQLite gallery storing face embeddings, not photographs."""
from __future__ import annotations
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'data' / 'faces.sqlite3'
NAME_PATTERN = re.compile(r'^[\w .\-\u00C0-\uFFFF]{2,64}$', re.UNICODE)


class Gallery:
    def __init__(self, path: Path = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS people (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS samples (id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE, embedding TEXT NOT NULL, created_at TEXT NOT NULL)')

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def list_people(self):
        with self.lock, self._connect() as db:
            results = db.execute('SELECT p.id,p.name,p.created_at,COUNT(s.id) FROM people p LEFT JOIN samples s ON s.person_id=p.id GROUP BY p.id ORDER BY p.name COLLATE NOCASE').fetchall()
        return [{"id": r[0], "name": r[1], "created_at": r[2], "samples": r[3]} for r in results]

    def enroll(self, name, feature):
        if not NAME_PATTERN.fullmatch(str(name).strip()):
            raise ValueError('Name must be 2–64 characters (letters, numbers, spaces, . - _).')
        arr = np.asarray(feature, dtype=np.float32)
        if arr.ndim != 1 or arr.size < 32 or not np.isfinite(arr).all():
            raise ValueError('Invalid recognition feature.')
        name = name.strip()
        moment = datetime.now(timezone.utc).isoformat()
        with self.lock, self._connect() as db:
            db.execute('INSERT OR IGNORE INTO people (name,created_at) VALUES (?,?)', (name, moment))
            person_id = db.execute('SELECT id FROM people WHERE name = ? COLLATE NOCASE', (name,)).fetchone()[0]
            samples = db.execute('SELECT count(*) FROM samples WHERE person_id=?', (person_id,)).fetchone()[0]
            if samples >= 8:
                raise ValueError('Maximum 8 samples per person. Delete and re-enroll to replace.')
            db.execute('INSERT INTO samples (person_id,embedding,created_at) VALUES (?,?,?)', (person_id,json.dumps(arr.tolist()),moment))
        return person_id

    def match(self, feature, threshold: float = 0.45):
        """Conservative default; score is cosine similarity, not probability."""
        vec = np.asarray(feature, dtype=np.float32)
        if vec.ndim != 1 or not np.isfinite(vec).all():
            return None
        length = np.linalg.norm(vec)
        if length <= 0: return None
        vec = vec / length
        with self.lock, self._connect() as db:
            rows = db.execute('SELECT p.id,p.name,s.embedding FROM samples s JOIN people p ON p.id=s.person_id').fetchall()
        best = None
        for person_id, name, encoded in rows:
            try:
                known = np.asarray(json.loads(encoded), dtype=np.float32)
                if known.shape != vec.shape: continue
                score = float(np.dot(vec, known / max(float(np.linalg.norm(known)), 1e-8)))
                if best is None or score > best['similarity']:
                    best = {'id': person_id, 'name': name, 'similarity': round(score, 3)}
            except (ValueError, TypeError):
                continue
        return best if best and best['similarity'] >= threshold else None

    def delete(self, person_id: int):
        with self.lock, self._connect() as db:
            cur = db.execute('DELETE FROM people WHERE id=?', (person_id,))
            return cur.rowcount > 0

    def delete_all(self):
        with self.lock, self._connect() as db:
            db.execute('DELETE FROM people')
