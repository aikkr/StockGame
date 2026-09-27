import json
import os
import random
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv


class UserDatabase:
    def __init__(self, path: str | Path | None = None):
        load_dotenv()
        configured_path = path or os.getenv('STOCKGAME_DB_PATH')
        self.path = (
            Path(configured_path)
            if configured_path
            else Path(__file__).with_name('stockgame.db')
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
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

    def _create_tables(self) -> None:
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
                '''
            )

    def _generateId(self) -> int:
        while True:
            user_id = random.SystemRandom().randint(100000000, 999999999)
            with self._connect() as connection:
                exists = connection.execute('SELECT 1 FROM users WHERE id = ?', (user_id,)).fetchone()
            if not exists:
                return user_id

    def addUser(self, name: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        user = {
            'id': self._generateId(),
            'name': name,
            'creationTime': now,
            'lastLogin': now,
            'saves': {},
        }
        with self._connect() as connection:
            connection.execute(
                'INSERT INTO users (id, name, creation_time, last_login) VALUES (?, ?, ?, ?)',
                (user['id'], user['name'], now, now),
            )
        return user

    def getUser(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if row is None:
                return None
            save_rows = connection.execute(
                'SELECT save_name, data FROM saves WHERE user_id = ?', (user_id,)
            ).fetchall()
        saves = {}
        for save in save_rows:
            try:
                saves[save['save_name']] = json.loads(save['data'])
            except json.JSONDecodeError:
                continue
        return {
            'id': row['id'],
            'name': row['name'],
            'creationTime': row['creation_time'],
            'lastLogin': row['last_login'],
            'saves': saves,
        }

    def login(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.now(timezone.utc).isoformat(), user_id),
            )

    def addSave(self, user_id: int, save_name: str, stocks: dict) -> None:
        data = json.dumps(stocks, separators=(',', ':'))
        with self._connect() as connection:
            connection.execute(
                '''
                INSERT INTO saves (user_id, save_name, data) VALUES (?, ?, ?)
                ON CONFLICT(user_id, save_name) DO UPDATE SET data = excluded.data
                ''',
                (user_id, save_name, data),
            )

    def getSave(self, user_id: int, save_name: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT data FROM saves WHERE user_id = ? AND save_name = ?',
                (user_id, save_name),
            ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row['data'])
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def deleteSave(self, user_id: int, save_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                'DELETE FROM saves WHERE user_id = ? AND save_name = ?',
                (user_id, save_name),
            )

    def addSession(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                'INSERT INTO sessions (token, user_id, created_at, last_seen) VALUES (?, ?, ?, ?)',
                (token, user_id, now, now),
            )
        return token

    def getUserBySession(self, token: str | None) -> dict | None:
        if not token or not isinstance(token, str):
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
