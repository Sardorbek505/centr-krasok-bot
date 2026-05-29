"""
SQLite база данных для аналитики бота.
Хранит: пользователей, кол-во сообщений, оценки ответов.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

DB_PATH = Path("bot_analytics.db")
logger = logging.getLogger(__name__)


def init_db() -> None:
    """Создаёт таблицы при первом запуске."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                first_seen  TEXT,
                last_seen   TEXT,
                msg_count   INTEGER DEFAULT 0,
                voice_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                rating      TEXT,   -- 'up' | 'down'
                question    TEXT,
                answer      TEXT,
                created_at  TEXT
            );
        """)
    logger.info("Database initialized: %s", DB_PATH)


def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    """Создаёт или обновляет запись пользователя."""
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_seen  = excluded.last_seen
        """, (user_id, username, first_name, now, now))


def increment_message(user_id: int, is_voice: bool = False) -> None:
    """Увеличивает счётчик сообщений пользователя."""
    with sqlite3.connect(DB_PATH) as conn:
        if is_voice:
            conn.execute("""
                UPDATE users SET msg_count = msg_count + 1,
                                 voice_count = voice_count + 1,
                                 last_seen = ?
                WHERE user_id = ?
            """, (datetime.now().isoformat(timespec="seconds"), user_id))
        else:
            conn.execute("""
                UPDATE users SET msg_count = msg_count + 1,
                                 last_seen = ?
                WHERE user_id = ?
            """, (datetime.now().isoformat(timespec="seconds"), user_id))


def save_feedback(user_id: int, rating: str, question: str, answer: str) -> None:
    """Сохраняет оценку пользователя."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO feedback (user_id, rating, question, answer, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, rating, question[:500], answer[:500],
              datetime.now().isoformat(timespec="seconds")))


def get_stats() -> dict:
    """Возвращает общую статистику бота."""
    with sqlite3.connect(DB_PATH) as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_messages = conn.execute("SELECT SUM(msg_count) FROM users").fetchone()[0] or 0
        total_voice = conn.execute("SELECT SUM(voice_count) FROM users").fetchone()[0] or 0
        active_today = conn.execute("""
            SELECT COUNT(*) FROM users
            WHERE last_seen >= date('now')
        """).fetchone()[0]
        thumbs_up = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = 'up'"
        ).fetchone()[0]
        thumbs_down = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating = 'down'"
        ).fetchone()[0]

    total_feedback = thumbs_up + thumbs_down
    satisfaction = (
        round(thumbs_up / total_feedback * 100) if total_feedback > 0 else 0
    )

    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "total_voice": total_voice,
        "active_today": active_today,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "satisfaction": satisfaction,
    }
