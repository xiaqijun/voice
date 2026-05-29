"""会话持久化存储 - SQLite 实现"""

import sqlite3
import uuid
import os
import threading
from typing import List, Dict, Optional
from datetime import datetime


class SessionStore:
    """SQLite 会话存储"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "sessions.db")
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        """)
        conn.commit()

    def create_session(self) -> str:
        """创建新会话，返回 session_id"""
        session_id = str(uuid.uuid4())
        conn = self._get_conn()
        conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        conn.commit()
        return session_id

    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        conn = self._get_conn()
        row = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return row is not None

    def get_or_create(self, session_id: Optional[str] = None) -> str:
        """有则返回，无则创建"""
        if session_id and self.session_exists(session_id):
            return session_id
        return self.create_session()

    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """获取最近 N 条消息"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def append_message(self, session_id: str, role: str, content: str):
        """追加一条消息"""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.execute(
            "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )
        conn.commit()

    def clear_session(self, session_id: str):
        """清空会话消息"""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

    def list_sessions(self) -> List[Dict]:
        """列出所有会话"""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT s.id, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count,
                   (SELECT content FROM messages WHERE session_id = s.id ORDER BY id DESC LIMIT 1) as last_message
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, session_id: str):
        """删除会话及关联消息"""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
