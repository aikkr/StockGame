import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from server.config import PROJECT_ROOT


class UserDatabase:
    def __init__(self, path=None):
        configured_path = path or os.getenv('STOCKGAME_DB_PATH')
        if configured_path:
            self.path = Path(configured_path)
        else:
            self.path = Path(__file__).with_name('stockgame.db')
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_tables(self):
        with self._connect() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    creation_time TEXT NOT NULL,
                    last_login TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS saves (
                    user_id INTEGER NOT NULL,
                    save_name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    PRIMARY KEY (user_id, save_name),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS market_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data TEXT NOT NULL
                );
                '''
            )

    def addUser(self, name):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:

            result = connection.execute(
                'INSERT INTO users (name, creation_time, last_login) VALUES (?, ?, ?)',
                (name, now, now),
            )
            user_id = result.lastrowid
        return {'id': user_id, 'name': name, 'creationTime': now, 'lastLogin': now}

    def getUser(self, user_id):
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if row is None:
                return None
        return {
            'id': row['id'],
            'name': row['name'],
            'creationTime': row['creation_time'],
            'lastLogin': row['last_login'],
        }

    def login(self, user_id):
        with self._connect() as connection:
            connection.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.now(timezone.utc).isoformat(), user_id),
            )

    def addSave(self, user_id, save_name, stocks, expected=None):
        data = json.dumps(stocks)
        with self._connect() as connection:
            if expected is not None:
                connection.execute('BEGIN IMMEDIATE')
                row = connection.execute(
                    'SELECT data FROM saves WHERE user_id = ? AND save_name = ?',
                    (user_id, save_name),
                ).fetchone()
                current = {}
                if row:
                    current = json.loads(row['data'])
                if current != expected:
                    raise ValueError('Progress changed in another tab. Refresh this page before continuing.')
            connection.execute(
                '''
                INSERT INTO saves (user_id, save_name, data) VALUES (?, ?, ?)
                ON CONFLICT(user_id, save_name) DO UPDATE SET data = excluded.data
                ''',
                (user_id, save_name, data),
            )

    def getSave(self, user_id, save_name):
        with self._connect() as connection:
            row = connection.execute(
                'SELECT data FROM saves WHERE user_id = ? AND save_name = ?',
                (user_id, save_name),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row['data'])

    def save_market(self, stocks):
        data = json.dumps(stocks)
        with self._connect() as connection:
            connection.execute(
                'INSERT INTO market_state (id, data) VALUES (1, ?) '
                'ON CONFLICT(id) DO UPDATE SET data = excluded.data',
                (data,),
            )

    def load_market(self):
        with self._connect() as connection:
            row = connection.execute('SELECT data FROM market_state WHERE id = 1').fetchone()
        if row:
            return json.loads(row['data'])
        return {}

    def addSession(self, user_id):
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                'INSERT INTO sessions (token, user_id, created_at, last_seen) VALUES (?, ?, ?, ?)',
                (token, user_id, now, now),
            )
        return token

    def getUserBySession(self, token):
        if not token:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                'SELECT user_id FROM sessions WHERE token = ?', (token,)
            ).fetchone()
            if row is None:
                return None
            connection.execute('UPDATE sessions SET last_seen = ? WHERE token = ?', (now, token))
        return self.getUser(row['user_id'])
