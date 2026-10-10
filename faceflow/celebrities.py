"""Opt-in, local celebrity reference gallery. No face photos are persisted.

References can be uploaded by a user or fetched, upon explicit request, as
Wikipedia article thumbnails. Matches are entertainment-only nearest neighbors,
not claims of identity, kinship or calibrated percent similarity.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from .storage import NAME_PATTERN, ROOT

STARTER_NAMES = [
    'Shah Rukh Khan', 'Deepika Padukone', 'Hrithik Roshan', 'Alia Bhatt',
    'Virat Kohli', 'Priyanka Chopra', 'Aishwarya Rai Bachchan',
    'Cristiano Ronaldo', 'Lionel Messi', 'Zendaya', 'Tom Holland',
    'Emma Watson', 'Taylor Swift', 'Leonardo DiCaprio', 'Selena Gomez',
    'Ranveer Singh',
]

# Curated *names*, not a bundled biometric database. The user must opt in
# to downloading portraits and some pages have no usable single-face image.
EXTENDED_NAMES = list(dict.fromkeys(STARTER_NAMES + [
    'Amitabh Bachchan', 'Aamir Khan', 'Salman Khan', 'Kareena Kapoor Khan',
    'Katrina Kaif', 'Anushka Sharma', 'Kiara Advani', 'Shraddha Kapoor',
    'Vicky Kaushal', 'Kartik Aaryan', 'Varun Dhawan', 'Janhvi Kapoor',
    'Rashmika Mandanna', 'Samantha Ruth Prabhu', 'Allu Arjun', 'Rajinikanth',
    'Rohit Sharma', 'Jasprit Bumrah', 'MS Dhoni', 'Sachin Tendulkar',
    'Neeraj Chopra', 'P. V. Sindhu', 'Smriti Mandhana',
    'Robert Downey Jr.', 'Chris Hemsworth', 'Chris Evans (actor)',
    'Scarlett Johansson', 'Jennifer Lawrence', 'Angelina Jolie',
    'Brad Pitt', 'Ryan Reynolds', 'Ryan Gosling', 'Margot Robbie',
    'Anne Hathaway', 'Keanu Reeves', 'Dwayne Johnson', 'Tom Cruise',
    'Millie Bobby Brown', 'Jenna Ortega', 'Timothée Chalamet',
    'Billie Eilish', 'Ariana Grande', 'Dua Lipa', 'Ed Sheeran',
    'Beyoncé', 'Rihanna', 'Justin Bieber', 'Lady Gaga',
    'Kylian Mbappé', 'Neymar', 'Erling Haaland', 'Mohamed Salah',
    'Serena Williams', 'Roger Federer', 'Lewis Hamilton',
]))

class CelebrityGallery:
    def __init__(self, path: Path | None = None):
        self.path = Path(path or (ROOT / 'data' / 'celebrity_refs.sqlite3'))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS celebrity_refs ('
                       'id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, '
                       'embedding TEXT NOT NULL, credit_url TEXT NOT NULL, created_at TEXT NOT NULL)')

    def _db(self):
        return sqlite3.connect(self.path, timeout=8)

    def list_refs(self):
        with self.lock, self._db() as db:
            rows = db.execute('SELECT id,name,credit_url FROM celebrity_refs ORDER BY name COLLATE NOCASE').fetchall()
        return [{'id': row[0], 'name': row[1], 'credit_url': row[2]} for row in rows]

    def add(self, name, embedding, credit_url=''):
        name = str(name).strip()
        if not NAME_PATTERN.fullmatch(name):
            raise ValueError('Name must be 2–64 characters.')
        vec = np.asarray(embedding, dtype=np.float32)
        if vec.ndim != 1 or vec.size < 32 or not np.isfinite(vec).all():
            raise ValueError('Invalid face reference.')
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            raise ValueError('Empty face reference.')
        url = str(credit_url)[:500]
        with self.lock, self._db() as db:
            db.execute('INSERT INTO celebrity_refs(name,embedding,credit_url,created_at) '
                       'VALUES(?,?,?,?) ON CONFLICT(name) DO UPDATE SET '
                       'embedding=excluded.embedding, credit_url=excluded.credit_url, '
                       'created_at=excluded.created_at',
                       (name, json.dumps((vec/norm).tolist()), url,
                        datetime.now(timezone.utc).isoformat()))

    def match(self, embedding, limit=3):
        if embedding is None:
            return []
        vec = np.asarray(embedding, dtype=np.float32)
        if vec.ndim != 1 or not np.isfinite(vec).all():
            return []
        norm = float(np.linalg.norm(vec))
        if norm < 1e-8:
            return []
        vec = vec / norm
        with self.lock, self._db() as db:
            rows = db.execute('SELECT name,embedding,credit_url FROM celebrity_refs').fetchall()
        scored = []
        for name, encoded, credit in rows:
            try:
                ref = np.asarray(json.loads(encoded), dtype=np.float32)
                if ref.shape != vec.shape or not np.isfinite(ref).all():
                    continue
                norm_ref = float(np.linalg.norm(ref))
                if norm_ref < 1e-8:
                    continue
                score = float(np.dot(vec, ref / norm_ref))
                if not math.isfinite(score):
                    continue
                scored.append({'name':name, 'similarity':round(score, 3), 'credit_url': credit})
            except (TypeError, ValueError):
                continue
        return sorted(scored, key=lambda x:x['similarity'], reverse=True)[:limit]

    def delete(self, ref_id):
        with self.lock, self._db() as db:
            cur=db.execute('DELETE FROM celebrity_refs WHERE id=?', (ref_id,))
            return cur.rowcount > 0

    def clear(self):
        with self.lock, self._db() as db:
            db.execute('DELETE FROM celebrity_refs')
