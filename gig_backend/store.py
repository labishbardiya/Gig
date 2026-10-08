import json
import sqlite3
import threading
import time
import uuid


class Store:
    """Single-user durable ledger. External side effects are never auto-retried."""
    def __init__(self, path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS calls (
          id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
          payload TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
          run_id TEXT, result TEXT);
        CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, messages TEXT NOT NULL);
        ''')
        # A prior process may have sent a call before crashing. Never replay it.
        self.db.execute("UPDATE calls SET state='unknown' WHERE state='submitting'")
        self.db.commit()

    def prepare(self, key, payload):
        encoded = json.dumps(payload, sort_keys=True)
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM calls WHERE request_key=?', (key,)).fetchone()
            if row:
                if row['payload'] != encoded:
                    raise ValueError('Idempotency key already belongs to different call details')
                return self.get_call(row['id'])
            ident = str(uuid.uuid4())
            self.db.execute('INSERT INTO calls(id,request_key,payload,state,created) VALUES(?,?,?,?,?)',
                            (ident, key, encoded, 'awaiting_approval', time.time()))
            return self.get_call(ident)

    def get_call(self, ident):
        with self.lock:
            row = self.db.execute('SELECT * FROM calls WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise KeyError(ident)
        result = dict(row)
        result['payload'] = json.loads(result['payload'])
        result['result'] = json.loads(result['result']) if result['result'] else None
        return result

    def claim(self, ident):
        with self.lock, self.db:
            row = self.get_call(ident)
            if row['state'] != 'awaiting_approval':
                return False
            if time.time() - row['created'] > 600:
                self.db.execute("UPDATE calls SET state='expired' WHERE id=?", (ident,))
                return False
            return self.db.execute("UPDATE calls SET state='submitting' WHERE id=? AND state='awaiting_approval'", (ident,)).rowcount == 1

    def finish(self, ident, state, run_id=None, result=None):
        with self.lock, self.db:
            self.db.execute('UPDATE calls SET state=?,run_id=COALESCE(?,run_id),result=? WHERE id=?',
                            (state, run_id, json.dumps(result), ident))

    def cancel(self, ident):
        with self.lock, self.db:
            return self.db.execute("UPDATE calls SET state='cancelled' WHERE id=? AND state='awaiting_approval'", (ident,)).rowcount == 1

    def save_note(self, text):
        ident = str(uuid.uuid4())
        with self.lock, self.db:
            self.db.execute('INSERT INTO notes VALUES(?,?,?)', (ident, text, time.time()))
        return ident

    def notes(self, query):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT * FROM notes WHERE instr(lower(text),lower(?))>0 ORDER BY created DESC LIMIT 100', (query,))]

    def forget(self, ident):
        with self.lock, self.db:
            return self.db.execute('DELETE FROM notes WHERE id=?', (ident,)).rowcount == 1

    def conversation(self, ident):
        with self.lock:
            row = self.db.execute('SELECT messages FROM sessions WHERE id=?', (ident,)).fetchone()
        return json.loads(row[0]) if row else []

    def save_conversation(self, ident, messages):
        with self.lock, self.db:
            self.db.execute('INSERT INTO sessions VALUES(?,?) ON CONFLICT(id) DO UPDATE SET messages=excluded.messages', (ident, json.dumps(messages[-20:])))

    def delete_conversation(self, ident):
        with self.lock, self.db:
            self.db.execute('DELETE FROM sessions WHERE id=?', (ident,))
