# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging
import pytz

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, path: str = "bot_data.db"):
        self.path = path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as c:
            try:
                c.execute("ALTER TABLE users ADD COLUMN data_warning_hiddify INTEGER DEFAULT 1;")
                logger.info("Column 'data_warning_hiddify' added to 'users' table.")
            except sqlite3.OperationalError:
                pass

            try:
                c.execute("ALTER TABLE users ADD COLUMN data_warning_marzban INTEGER DEFAULT 1;")
                logger.info("Column 'data_warning_marzban' added to 'users' table.")
            except sqlite3.OperationalError:
                pass

            c.executescript("""
                                CREATE TABLE IF NOT EXISTS users (
                                    user_id INTEGER PRIMARY KEY,
                                    username TEXT,
                                    first_name TEXT,
                                    birthday DATE,
                                    last_name TEXT,
                                    daily_reports INTEGER DEFAULT 1,
                                    expiry_warnings INTEGER DEFAULT 1,
                                    data_warning_hiddify INTEGER DEFAULT 1,
                                    data_warning_marzban INTEGER DEFAULT 1,
                                    admin_note TEXT
                                );
                                CREATE TABLE IF NOT EXISTS user_uuids (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    user_id INTEGER,
                                    uuid TEXT UNIQUE,
                                    name TEXT,
                                    is_active INTEGER DEFAULT 1,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    updated_at TIMESTAMP,
                                    first_connection_time TIMESTAMP,
                                    welcome_message_sent INTEGER DEFAULT 0,
                                    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
                                );
                                CREATE TABLE IF NOT EXISTS usage_snapshots (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    uuid_id INTEGER,
                                    hiddify_usage_gb REAL DEFAULT 0,
                                    marzban_usage_gb REAL DEFAULT 0,
                                    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    FOREIGN KEY(uuid_id) REFERENCES user_uuids(id) ON DELETE CASCADE
                                );
                                CREATE TABLE IF NOT EXISTS scheduled_messages (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    job_type TEXT NOT NULL,
                                    chat_id INTEGER NOT NULL,
                                    message_id INTEGER NOT NULL,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    UNIQUE(job_type, chat_id)
                                );
                                CREATE TABLE IF NOT EXISTS warning_log (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    uuid_id INTEGER NOT NULL,
                                    warning_type TEXT NOT NULL, -- e.g., 'expiry', 'low_data_hiddify'
                                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    UNIQUE(uuid_id, warning_type)
                                );
                                CREATE TABLE IF NOT EXISTS payments (
                                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    uuid_id INTEGER NOT NULL,
                                    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                    FOREIGN KEY(uuid_id) REFERENCES user_uuids(id) ON DELETE CASCADE
                                );
                                    CREATE INDEX IF NOT EXISTS idx_user_uuids_uuid ON user_uuids(uuid);
                                    CREATE INDEX IF NOT EXISTS idx_user_uuids_user_id ON user_uuids(user_id);
                                    CREATE INDEX IF NOT EXISTS idx_snapshots_uuid_id_taken_at ON usage_snapshots(uuid_id, taken_at);
                                    CREATE INDEX IF NOT EXISTS idx_scheduled_messages_job_type ON scheduled_messages(job_type);
                                    CREATE INDEX IF NOT EXISTS idx_warning_log_uuid_type ON warning_log(uuid_id, warning_type);
                            """)
        logger.info("SQLite schema and indexes are ready.")

    def add_usage_snapshot(self, uuid_id: int, hiddify_usage: float, marzban_usage: float) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO usage_snapshots (uuid_id, hiddify_usage_gb, marzban_usage_gb, taken_at) VALUES (?, ?, ?, ?)",
                (uuid_id, hiddify_usage, marzban_usage, datetime.now(pytz.utc))
            )

    def get_usage_since_midnight(self, uuid_id: int) -> Dict[str, float]:
        """Calculates daily usage for both panels with a single, simplified, and robust query."""
        tehran_tz = pytz.timezone("Asia/Tehran")
        today_midnight_tehran = datetime.now(tehran_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        today_midnight_utc = today_midnight_tehran.astimezone(pytz.utc)
        
        result = {'hiddify': 0.0, 'marzban': 0.0}

        with self._conn() as c:
            # *** FINAL FIX: Simplified and more robust query ***
            query = """
                SELECT
                    (MAX(hiddify_usage_gb) - MIN(hiddify_usage_gb)) as h_diff,
                    (MAX(marzban_usage_gb) - MIN(marzban_usage_gb)) as m_diff
                FROM usage_snapshots
                WHERE uuid_id = ? AND taken_at >= ?;
            """
            params = (uuid_id, today_midnight_utc)
            row = c.execute(query, params).fetchone()

            if row:
                # Use max(0, ...) to prevent negative results if usage resets during the day
                result['hiddify'] = max(0, row['h_diff'] or 0.0)
                result['marzban'] = max(0, row['m_diff'] or 0.0)

        return result
    
    def get_panel_usage_in_intervals(self, uuid_id: int, panel_name: str) -> Dict[int, float]:
        if panel_name not in ['hiddify_usage_gb', 'marzban_usage_gb']:
            return {}

        now_utc = datetime.now(pytz.utc)
        intervals = {3: 0.0, 6: 0.0, 12: 0.0, 24: 0.0}
        
        with self._conn() as c:
            for hours in intervals.keys():
                time_ago = now_utc - timedelta(hours=hours)
                
                query = f"""
                    SELECT
                        (SELECT {panel_name} FROM usage_snapshots WHERE uuid_id = ? AND taken_at >= ? ORDER BY taken_at ASC LIMIT 1) as start_usage,
                        (SELECT {panel_name} FROM usage_snapshots WHERE uuid_id = ? AND taken_at >= ? ORDER BY taken_at DESC LIMIT 1) as end_usage
                """
                params = (uuid_id, time_ago, uuid_id, time_ago)
                row = c.execute(query, params).fetchone()
                
                if row and row['start_usage'] is not None and row['end_usage'] is not None:
                    intervals[hours] = max(0, row['end_usage'] - row['start_usage'])
                    
        return intervals
        
    def log_warning(self, uuid_id: int, warning_type: str):
        with self._conn() as c:
            c.execute(
                "INSERT INTO warning_log (uuid_id, warning_type, sent_at) VALUES (?, ?, ?) "
                "ON CONFLICT(uuid_id, warning_type) DO UPDATE SET sent_at=excluded.sent_at",
                (uuid_id, warning_type, datetime.now(pytz.utc))
            )

    def has_recent_warning(self, uuid_id: int, warning_type: str, hours: int = 24) -> bool:
        time_ago = datetime.now(pytz.utc) - timedelta(hours=hours)
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM warning_log WHERE uuid_id = ? AND warning_type = ? AND sent_at >= ?",
                (uuid_id, warning_type, time_ago)
            ).fetchone()
            return row is not None

    def get_user_ids_by_uuids(self, uuids: List[str]) -> List[int]:
        if not uuids: return []
        placeholders = ','.join('?' for _ in uuids)
        query = f"SELECT DISTINCT user_id FROM user_uuids WHERE uuid IN ({placeholders})"
        with self._conn() as c:
            rows = c.execute(query, uuids).fetchall()
            return [row['user_id'] for row in rows]
        
    def get_uuid_id_by_uuid(self, uuid_str: str) -> Optional[int]:
        with self._conn() as c:
            row = c.execute("SELECT id FROM user_uuids WHERE uuid = ?", (uuid_str,)).fetchone()
            return row['id'] if row else None

    def get_usage_since_midnight_by_uuid(self, uuid_str: str) -> Dict[str, float]:
        """Convenience function to get daily usage directly by UUID string."""
        uuid_id = self.get_uuid_id_by_uuid(uuid_str)
        if uuid_id:
            return self.get_usage_since_midnight(uuid_id)
        return {'hiddify': 0.0, 'marzban': 0.0}


    def add_or_update_scheduled_message(self, job_type: str, chat_id: int, message_id: int):
        with self._conn() as c:
            c.execute(
                "INSERT INTO scheduled_messages(job_type, chat_id, message_id) VALUES(?,?,?) "
                "ON CONFLICT(job_type, chat_id) DO UPDATE SET message_id=excluded.message_id, created_at=CURRENT_TIMESTAMP",
                (job_type, chat_id, message_id)
            )

    def get_scheduled_messages(self, job_type: str) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM scheduled_messages WHERE job_type=?", (job_type,)).fetchall()
            return [dict(r) for r in rows]

    def delete_scheduled_message(self, job_id: int):
        with self._conn() as c:
            c.execute("DELETE FROM scheduled_messages WHERE id=?", (job_id,))
            
    def user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def add_or_update_user(self, user_id: int, username: Optional[str], first: Optional[str], last: Optional[str]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT INTO users(user_id, username, first_name, last_name) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name",
                (user_id, username, first, last),
            )

    def get_user_settings(self, user_id: int) -> Dict[str, bool]:
        with self._conn() as c:
            row = c.execute("SELECT daily_reports, expiry_warnings, data_warning_hiddify, data_warning_marzban FROM users WHERE user_id=?", (user_id,)).fetchone()
            if row:
                return {
                    'daily_reports': bool(row['daily_reports']), 
                    'expiry_warnings': bool(row['expiry_warnings']),
                    'data_warning_hiddify': bool(row['data_warning_hiddify']),
                    'data_warning_marzban': bool(row['data_warning_marzban'])
                }
            return {
                'daily_reports': True, 'expiry_warnings': True, 
                'data_warning_hiddify': True, 'data_warning_marzban': True
            }

    def update_user_setting(self, user_id: int, setting: str, value: bool) -> None:
            if setting not in ['daily_reports', 'expiry_warnings', 'data_warning_hiddify', 'data_warning_marzban']: return
            with self._conn() as c:
                c.execute(f"UPDATE users SET {setting}=? WHERE user_id=?", (int(value), user_id))

    def add_uuid(self, user_id: int, uuid_str: str, name: str) -> str:
        uuid_str = uuid_str.lower()
        with self._conn() as c:
            existing = c.execute("SELECT * FROM user_uuids WHERE uuid = ?", (uuid_str,)).fetchone()
            if existing:
                if existing['is_active']:
                    if existing['user_id'] == user_id:
                        return "این UUID در حال حاضر در لیست شما فعال است."
                    else:
                        return "این UUID قبلاً توسط کاربر دیگری ثبت شده است."
                else:
                    if existing['user_id'] == user_id:
                        c.execute("UPDATE user_uuids SET is_active = 1, name = ?, updated_at = CURRENT_TIMESTAMP WHERE uuid = ?", (name, uuid_str))
                        return "✅ اکانت شما که قبلاً حذف شده بود، با موفقیت دوباره فعال شد."
                    else:
                        return "این UUID متعلق به کاربر دیگری بوده و در حال حاضر غیرفعال است. امکان ثبت آن وجود ندارد."
            else:
                c.execute(
                    "INSERT INTO user_uuids (user_id, uuid, name) VALUES (?, ?, ?)",
                    (user_id, uuid_str, name)
                )
                return "✅ اکانت شما با موفقیت ثبت شد."

    def uuids(self, user_id: int) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM user_uuids WHERE user_id=? AND is_active=1 ORDER BY created_at", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def uuid_by_id(self, user_id: int, uuid_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM user_uuids WHERE user_id=? AND id=? AND is_active=1", (user_id, uuid_id)).fetchone()
            return dict(row) if row else None

    def deactivate_uuid(self, uuid_id: int) -> bool:
        with self._conn() as c:
            res = c.execute("UPDATE user_uuids SET is_active = 0 WHERE id = ?", (uuid_id,))
            return res.rowcount > 0

    def delete_user_by_uuid(self, uuid: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM user_uuids WHERE uuid=?", (uuid,))

    def all_active_uuids(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT id, user_id, uuid, created_at FROM user_uuids WHERE is_active=1").fetchall()
            return [dict(r) for r in rows]
            
    def get_all_user_ids(self) -> list[int]:
        with self._conn() as c:
            return [r['user_id'] for r in c.execute("SELECT user_id FROM users")]
        
    def get_all_bot_users(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT user_id, username, first_name, last_name FROM users ORDER BY user_id").fetchall()
            return [dict(r) for r in rows]
        
    def update_user_birthday(self, user_id: int, birthday_date: datetime.date):
        with self._conn() as c:
            c.execute("UPDATE users SET birthday = ? WHERE user_id = ?", (birthday_date, user_id))

    def get_users_with_birthdays(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("""
                SELECT user_id, first_name, username, birthday FROM users
                WHERE birthday IS NOT NULL
                ORDER BY strftime('%m-%d', birthday)
            """).fetchall()
            return [dict(r) for r in rows]
        
    def get_user_id_by_uuid(self, uuid: str) -> Optional[int]:
        with self._conn() as c:
            row = c.execute("SELECT user_id FROM user_uuids WHERE uuid = ?", (uuid,)).fetchone()
            return row['user_id'] if row else None

    def reset_user_birthday(self, user_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE users SET birthday = NULL WHERE user_id = ?", (user_id,))

    def delete_user_snapshots(self, uuid_id: int) -> int:
        with self._conn() as c:
            cursor = c.execute("DELETE FROM usage_snapshots WHERE uuid_id = ?", (uuid_id,))
            return cursor.rowcount
    
    def get_todays_birthdays(self) -> list:
        today = datetime.now(pytz.utc)
        today_month_day = f"{today.month:02d}-{today.day:02d}"
        with self._conn() as c:
            rows = c.execute(
                "SELECT user_id FROM users WHERE strftime('%m-%d', birthday) = ?",
                (today_month_day,)
            ).fetchall()
            return [row['user_id'] for row in rows]

    def vacuum_db(self) -> None:
        with self._conn() as c:
            c.execute("VACUUM")

    def get_bot_user_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT u.user_id, u.first_name, u.username
            FROM users u
            JOIN user_uuids uu ON u.user_id = uu.user_id
            WHERE uu.uuid = ?
        """
        with self._conn() as c:
            row = c.execute(query, (uuid,)).fetchone()
            return dict(row) if row else None

    def get_uuid_to_user_id_map(self) -> Dict[str, int]:
        with self._conn() as c:
            rows = c.execute("SELECT uuid, user_id FROM user_uuids WHERE is_active=1").fetchall()
            return {row['uuid']: row['user_id'] for row in rows}
        
    def get_uuid_to_bot_user_map(self) -> Dict[str, Dict[str, Any]]:
        query = """
            SELECT uu.uuid, u.user_id, u.first_name, u.username
            FROM user_uuids uu
            LEFT JOIN users u ON uu.user_id = u.user_id
            WHERE uu.is_active = 1
        """
        result_map = {}
        with self._conn() as c:
            rows = c.execute(query).fetchall()
            for row in rows:
                if row['uuid'] not in result_map:
                    result_map[row['uuid']] = dict(row)
        return result_map
    
    def delete_daily_snapshots(self, uuid_id: int) -> None:
        """Deletes all usage snapshots for a given uuid_id that were taken today (UTC)."""
        today_start_utc = datetime.now(pytz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with self._conn() as c:
            c.execute("DELETE FROM usage_snapshots WHERE uuid_id = ? AND taken_at >= ?", (uuid_id, today_start_utc))
            logger.info(f"Deleted daily snapshots for uuid_id {uuid_id}.")

    def set_first_connection_time(self, uuid_id: int, time: datetime):
        with self._conn() as c:
            c.execute("UPDATE user_uuids SET first_connection_time = ? WHERE id = ?", (time, uuid_id))

    def mark_welcome_message_as_sent(self, uuid_id: int):
        with self._conn() as c:
            c.execute("UPDATE user_uuids SET welcome_message_sent = 1 WHERE id = ?", (uuid_id,))

    def add_payment_record(self, uuid_id: int) -> bool:
        """یک رکورد پرداخت برای کاربر با تاریخ فعلی ثبت می‌کند."""
        with self._conn() as c:
            c.execute("INSERT INTO payments (uuid_id, payment_date) VALUES (?, ?)",
                      (uuid_id, datetime.now(pytz.utc)))
            return True

    def get_payment_history(self) -> List[Dict[str, Any]]:
        """لیست تمام کاربرانی که پرداخت ثبت‌شده دارند را به همراه آخرین تاریخ پرداختشان برمی‌گرداند."""
        query = """
            SELECT uu.name, p.payment_date
            FROM payments p
            JOIN user_uuids uu ON p.uuid_id = uu.id
            WHERE uu.is_active = 1
            GROUP BY p.uuid_id
            ORDER BY p.payment_date DESC;
        """
        with self._conn() as c:
            rows = c.execute(query).fetchall()
            return [dict(r) for r in rows]
        
    def get_user_payment_history(self, uuid_id: int) -> List[Dict[str, Any]]:
            """تمام رکوردهای پرداخت برای یک کاربر خاص را برمی‌گرداند."""
            with self._conn() as c:
                rows = c.execute("SELECT payment_date FROM payments WHERE uuid_id = ? ORDER BY payment_date DESC", (uuid_id,)).fetchall()
                return [dict(r) for r in rows]

    def update_user_note(self, user_id: int, note: Optional[str]) -> None:
        """Updates or removes the admin note for a given user."""
        with self._conn() as c:
            c.execute("UPDATE users SET admin_note = ? WHERE user_id = ?", (note, user_id))

db = DatabaseManager()