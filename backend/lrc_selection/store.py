import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from fastapi import HTTPException

WEDDING = {'id': 'wedding', 'name': 'Wedding', 'version': 1, 'criteria': [
    'Preserve different situations and compositions',
    'Keep unique images even when imperfect',
    'Prefer meaningful variations over duplicates',
]}

NATURE = {'id': 'nature', 'name': 'Nature and wildlife', 'version': 1, 'subject_query': 'animals and birds', 'criteria': [
    'Preserve different species, environments and actions',
    'Compare pose variations before reducing bursts',
]}

class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = root / 'selection.sqlite3'
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise RuntimeError('App database was created by a newer version')
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS services(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, service_id TEXT NOT NULL, body TEXT NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO presets VALUES(?,?)', ('wedding', json.dumps(WEDDING)))
            db.execute('INSERT OR IGNORE INTO presets VALUES(?,?)', ('nature', json.dumps(NATURE)))
            if version == 0:
                db.execute('PRAGMA user_version=1')
        self.path.chmod(0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, sid, db=None):
        if db is None:
            with self.connect() as conn:
                return self.get(sid, conn)
        row = db.execute('SELECT body FROM services WHERE id=?', (sid,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Service not found')
        return json.loads(row['body'])

    def put(self, db, service):
        db.execute('INSERT OR REPLACE INTO services VALUES(?,?)', (service['id'], json.dumps(service, ensure_ascii=False)))

    @staticmethod
    def check_revision(service, revision):
        if service['revision'] != revision:
            raise HTTPException(409, 'The revision has changed. Reload the service.')

    def preview_path(self, sid, pid):
        # Never derive paths from original filenames or externally supplied paths.
        import hashlib
        key = hashlib.sha256(f'{sid}\0{pid}'.encode()).hexdigest()
        return self.root / 'previews' / f'{key}.jpg'

    def recover_jobs(self):
        with self.transaction() as db:
            rows = db.execute('SELECT body FROM services').fetchall()
            for row in rows:
                service = json.loads(row['body'])
                if service.get('job') and service['job']['status'] in ('queued', 'running'):
                    service['job']['status'] = 'interrupted'
                    service['job']['error'] = 'Analysis interrupted. Start again to resume from saved data.'
                    service['status'] = 'ready'
                    service['revision'] += 1
                    self.put(db, service)
