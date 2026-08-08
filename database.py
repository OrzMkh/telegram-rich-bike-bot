import os
import sqlite3
import datetime
from contextlib import contextmanager

# ─── PostgreSQL support (if DATABASE_URL is set, use Postgres; else SQLite) ───
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL and HAS_PSYCOPG2)


# ─── Connection context manager ───────────────────────────────────────────────

@contextmanager
def get_connection(db_path="bike_reports.db"):
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield _PGConnWrapper(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class _PGConnWrapper:
    """Wraps psycopg2 connection to behave like sqlite3.Connection."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _PGCursorWrapper(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class _PGCursorWrapper:
    """Wraps psycopg2 cursor to behave like sqlite3.Cursor."""
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        sql = self._adapt_sql(sql)
        if params:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        self.rowcount = self._cur.rowcount
        # Try to get lastrowid for INSERT ... RETURNING id
        try:
            row = self._cur.fetchone()
            if row and "id" in row:
                self.lastrowid = row["id"]
        except Exception:
            pass

    def fetchone(self):
        row = self._cur.fetchone()
        return dict(row) if row else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [dict(r) for r in rows] if rows else []

    def _adapt_sql(self, sql):
        # Replace ? with %s for psycopg2
        sql = sql.replace("?", "%s")
        # SQLite specific → PG equivalent
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        sql = sql.replace("AUTOINCREMENT", "")
        # ON CONFLICT upsert syntax
        sql = sql.replace(
            "INSERT INTO users (user_id, username, full_name, role, assigned_city, is_active, created_at)\n            VALUES (%s, %s, %s, %s, %s, 1, %s)\n            ON CONFLICT(user_id) DO UPDATE SET",
            "INSERT INTO users (user_id, username, full_name, role, assigned_city, is_active, created_at)\n            VALUES (%s, %s, %s, %s, %s, 1, %s)\n            ON CONFLICT (user_id) DO UPDATE SET"
        )
        sql = sql.replace("ON CONFLICT(user_id)", "ON CONFLICT (user_id)")
        # PRAGMA is sqlite-only; make it a no-op for PG
        if "PRAGMA" in sql:
            sql = "SELECT 1"
        return sql


# ─── DB Init ──────────────────────────────────────────────────────────────────

def init_db(db_path="bike_reports.db"):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        if USE_POSTGRES:
            # PostgreSQL: use SERIAL and standard syntax
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cities (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    has_bike_types INTEGER DEFAULT 1,
                    total_bikes INTEGER DEFAULT 80,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'partner',
                    assigned_city TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bike_reports (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    username TEXT,
                    city TEXT DEFAULT '',
                    report_date TEXT NOT NULL,
                    issued TEXT NOT NULL,
                    returned TEXT NOT NULL,
                    total_in_trip TEXT NOT NULL,
                    new_bikes TEXT NOT NULL,
                    old_bikes TEXT NOT NULL,
                    broken_bikes TEXT NOT NULL,
                    return_reasons TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
            """)
        else:
            # SQLite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    has_bike_types INTEGER DEFAULT 1,
                    total_bikes INTEGER DEFAULT 80,
                    created_at TEXT NOT NULL
                )
            """)
            # Migration: Ensure columns exist
            cursor.execute("PRAGMA table_info(cities)")
            city_cols = [c[1] for c in cursor.fetchall()]
            if "has_bike_types" not in city_cols:
                cursor.execute("ALTER TABLE cities ADD COLUMN has_bike_types INTEGER DEFAULT 1")
            if "total_bikes" not in city_cols:
                cursor.execute("ALTER TABLE cities ADD COLUMN total_bikes INTEGER DEFAULT 80")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'partner',
                    assigned_city TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bike_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    city TEXT DEFAULT '',
                    report_date TEXT NOT NULL,
                    issued TEXT NOT NULL,
                    returned TEXT NOT NULL,
                    total_in_trip TEXT NOT NULL,
                    new_bikes TEXT NOT NULL,
                    old_bikes TEXT NOT NULL,
                    broken_bikes TEXT NOT NULL,
                    return_reasons TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("PRAGMA table_info(bike_reports)")
            columns = [column[1] for column in cursor.fetchall()]
            if "city" not in columns:
                cursor.execute("ALTER TABLE bike_reports ADD COLUMN city TEXT DEFAULT ''")

        conn.commit()

    # Pre-populate default cities
    default_cities = [
        ("Ташкент", 50, 0),
        ("Самарканд", 200, 0),
        ("Фергана", 80, 0),
        ("Андижан", 50, 0),
        ("Бухара", 30, 0),
        ("Навои", 30, 0),
        ("Карши", 30, 0),
        ("Ургенч", 30, 0),
        ("Нукус", 30, 0),
        ("Коканд", 25, 0),
        ("Наманган", 25, 0),
    ]
    for c_name, c_bikes, c_types in default_cities:
        add_city(c_name, has_bike_types=c_types, total_bikes=c_bikes, db_path=db_path)

    # Force auto-migration if legacy 1670 was saved
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur._cur.execute("UPDATE cities SET total_bikes = 50 WHERE name = 'Ташкент' AND total_bikes > 500")
        else:
            cur.execute("UPDATE cities SET total_bikes = 50 WHERE name = 'Ташкент' AND total_bikes > 500")
        conn.commit()

    # Pre-populate default partners (access to fill reports)
    default_partners = [
        6587381849,
        7792110579,
        5356085349,
        5196914934,
        6435381421,
        2386988,
    ]
    for uid in default_partners:
        authorize_user(
            user_id=uid,
            username=f"user_{uid}",
            full_name="Партнёр",
            role="partner",
            db_path=db_path
        )

# ─── Cities Management ────────────────────────────────────────────────────────

def add_city(name: str, has_bike_types: int = 0, total_bikes: int = 80, db_path="bike_reports.db") -> bool:
    name = name.strip()
    if not name:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if USE_POSTGRES:
            cursor._cur.execute("""
                INSERT INTO cities (name, has_bike_types, total_bikes, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    total_bikes = EXCLUDED.total_bikes,
                    has_bike_types = EXCLUDED.has_bike_types
            """, (name, has_bike_types, total_bikes, now))
        else:
            cursor.execute("SELECT id FROM cities WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE cities SET total_bikes = ?, has_bike_types = ? WHERE id = ?",
                    (total_bikes, has_bike_types, row["id"] if isinstance(row, dict) else row[0])
                )
            else:
                cursor.execute(
                    "INSERT INTO cities (name, has_bike_types, total_bikes, created_at) VALUES (?, ?, ?, ?)",
                    (name, has_bike_types, total_bikes, now)
                )
        conn.commit()
        return True


def toggle_city_bike_types(city_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute(
                "UPDATE cities SET has_bike_types = CASE WHEN has_bike_types = 1 THEN 0 ELSE 1 END WHERE id = %s",
                (city_id,)
            )
        else:
            cursor.execute(
                "UPDATE cities SET has_bike_types = CASE WHEN has_bike_types = 1 THEN 0 ELSE 1 END WHERE id = ?",
                (city_id,)
            )
        conn.commit()
        return True


def update_city_total_bikes(city_id: int, total_bikes: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("UPDATE cities SET total_bikes = %s WHERE id = %s", (total_bikes, city_id))
        else:
            cursor.execute("UPDATE cities SET total_bikes = ? WHERE id = ?", (total_bikes, city_id))
        conn.commit()
        return True


def delete_city(city_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("DELETE FROM cities WHERE id = %s", (city_id,))
        else:
            cursor.execute("DELETE FROM cities WHERE id = ?", (city_id,))
        conn.commit()
        return True


def get_all_cities(db_path="bike_reports.db") -> list:
    priority_order = ["Ташкент", "Самарканд", "Фергана", "Андижан", "Коканд", "Наманган"]
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("SELECT * FROM cities")
            cities = [dict(r) for r in cursor._cur.fetchall()]
        else:
            cursor.execute("SELECT * FROM cities")
            cities = [dict(r) for r in cursor.fetchall()]

    def sort_key(c):
        name = c["name"].strip()
        if name in priority_order:
            return (0, priority_order.index(name))
        return (1, name)

    return sorted(cities, key=sort_key)


def get_city_by_name(name: str, db_path="bike_reports.db"):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("SELECT * FROM cities WHERE name = %s", (name.strip(),))
            row = cursor._cur.fetchone()
        else:
            cursor.execute("SELECT * FROM cities WHERE name = ?", (name.strip(),))
            row = cursor.fetchone()
        return dict(row) if row else None


# ─── Users & Access Management ────────────────────────────────────────────────

def authorize_user(user_id: int, username: str = "", full_name: str = "", role: str = "partner", assigned_city: str = "", db_path="bike_reports.db") -> dict:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("""
                INSERT INTO users (user_id, username, full_name, role, assigned_city, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, 1, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    assigned_city = EXCLUDED.assigned_city,
                    is_active = 1
            """, (user_id, username, full_name, role, assigned_city, now))
        else:
            cursor.execute("""
                INSERT INTO users (user_id, username, full_name, role, assigned_city, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    role=excluded.role,
                    assigned_city=excluded.assigned_city,
                    is_active=1
            """, (user_id, username, full_name, role, assigned_city, now))
        conn.commit()
    return get_user(user_id, db_path=db_path)


def deauthorize_user(user_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("UPDATE users SET is_active = 0 WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True


def delete_user(user_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        else:
            cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        return True


def get_user(user_id: int, db_path="bike_reports.db"):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cursor._cur.fetchone()
        else:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        return dict(row) if row else None


def get_all_users(db_path="bike_reports.db") -> list:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(r) for r in cursor._cur.fetchall()]
        else:
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]


def is_user_authorized(user_id: int, username: str = None, admin_ids: list = None, db_path="bike_reports.db") -> bool:
    if is_user_admin(user_id, username, admin_ids, db_path):
        return True
    user = get_user(user_id, db_path=db_path)
    return bool(user and user.get("is_active") == 1)


def is_user_admin(user_id: int, username: str = None, admin_ids: list = None, db_path="bike_reports.db") -> bool:
    str_uid = str(user_id)
    if str_uid == "509067967":
        return True

    if admin_ids:
        str_uname = f"@{username}" if username else ""
        for a in admin_ids:
            clean_a = str(a).strip()
            if clean_a and (clean_a == str_uid or (clean_a.startswith("@") and clean_a.lower() == str_uname.lower())):
                return True

    user = get_user(user_id, db_path=db_path)
    if user:
        return bool(user.get("role") == "admin" and user.get("is_active") == 1)

    return False


# ─── Bike Reports ─────────────────────────────────────────────────────────────

def add_bike_report(report_data: dict, db_path="bike_reports.db") -> dict:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor._cur.execute("""
                INSERT INTO bike_reports (
                    user_id, username, city, report_date, issued, returned, total_in_trip,
                    new_bikes, old_bikes, broken_bikes, return_reasons, comment, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                report_data.get("user_id"),
                report_data.get("username"),
                report_data.get("city", ""),
                report_data.get("report_date"),
                report_data.get("issued"),
                report_data.get("returned"),
                report_data.get("total_in_trip"),
                report_data.get("new_bikes"),
                report_data.get("old_bikes"),
                report_data.get("broken_bikes"),
                report_data.get("return_reasons"),
                report_data.get("comment", ""),
                report_data.get("created_at"),
            ))
            row = cursor._cur.fetchone()
            report_id = row["id"] if row else None
        else:
            cursor.execute("""
                INSERT INTO bike_reports (
                    user_id, username, city, report_date, issued, returned, total_in_trip,
                    new_bikes, old_bikes, broken_bikes, return_reasons, comment, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_data.get("user_id"),
                report_data.get("username"),
                report_data.get("city", ""),
                report_data.get("report_date"),
                report_data.get("issued"),
                report_data.get("returned"),
                report_data.get("total_in_trip"),
                report_data.get("new_bikes"),
                report_data.get("old_bikes"),
                report_data.get("broken_bikes"),
                report_data.get("return_reasons"),
                report_data.get("comment", ""),
                report_data.get("created_at"),
            ))
            conn.commit()
            report_id = cursor.lastrowid

        res = dict(report_data)
        res["id"] = report_id
        return res


def get_bike_reports(city: str = None, limit: int = 50, db_path="bike_reports.db") -> list:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if USE_POSTGRES:
            if city:
                cursor._cur.execute(
                    "SELECT * FROM bike_reports WHERE city = %s ORDER BY id DESC LIMIT %s",
                    (city, limit)
                )
            else:
                cursor._cur.execute(
                    "SELECT * FROM bike_reports ORDER BY id DESC LIMIT %s",
                    (limit,)
                )
            return [dict(r) for r in cursor._cur.fetchall()]
        else:
            if city:
                cursor.execute(
                    "SELECT * FROM bike_reports WHERE city = ? ORDER BY id DESC LIMIT ?",
                    (city, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM bike_reports ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [dict(r) for r in cursor.fetchall()]
