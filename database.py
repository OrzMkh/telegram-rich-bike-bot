import sqlite3
import datetime
from contextlib import contextmanager

@contextmanager
def get_connection(db_path="bike_reports.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db(db_path="bike_reports.db"):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Cities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                has_bike_types INTEGER DEFAULT 1,
                total_bikes INTEGER DEFAULT 80,
                created_at TEXT NOT NULL
            )
        """)

        # Migration: Ensure 'has_bike_types' and 'total_bikes' columns exist
        cursor.execute("PRAGMA table_info(cities)")
        city_cols = [c[1] for c in cursor.fetchall()]
        if "has_bike_types" not in city_cols:
            cursor.execute("ALTER TABLE cities ADD COLUMN has_bike_types INTEGER DEFAULT 1")
        if "total_bikes" not in city_cols:
            cursor.execute("ALTER TABLE cities ADD COLUMN total_bikes INTEGER DEFAULT 80")

        # 2. Authorized Users / Roles table
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

        # 3. Bike Reports table
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
        
        # Ensure 'city' column exists if table was created previously
        cursor.execute("PRAGMA table_info(bike_reports)")
        columns = [column[1] for column in cursor.fetchall()]
        if "city" not in columns:
            cursor.execute("ALTER TABLE bike_reports ADD COLUMN city TEXT DEFAULT ''")

        conn.commit()

    # Pre-populate default cities from Google Sheet tabs if missing
    default_cities = [
        ("Ташкент", 1670, 0),
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

# --- Cities Management ---
def add_city(name: str, has_bike_types: int = 0, total_bikes: int = 80, db_path="bike_reports.db") -> bool:
    name = name.strip()
    if not name:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT id FROM cities WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE cities SET total_bikes = ?, has_bike_types = ? WHERE id = ?", (total_bikes, has_bike_types, row["id"]))
        else:
            cursor.execute("INSERT INTO cities (name, has_bike_types, total_bikes, created_at) VALUES (?, ?, ?, ?)", (name, has_bike_types, total_bikes, now))
        conn.commit()
        return True

def toggle_city_bike_types(city_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE cities SET has_bike_types = CASE WHEN has_bike_types = 1 THEN 0 ELSE 1 END WHERE id = ?", (city_id,))
        conn.commit()
        return cursor.rowcount > 0

def update_city_total_bikes(city_id: int, total_bikes: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE cities SET total_bikes = ? WHERE id = ?", (total_bikes, city_id))
        conn.commit()
        return cursor.rowcount > 0

def delete_city(city_id: int, db_path="bike_reports.db") -> bool:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM cities WHERE id = ?", (city_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_cities(db_path="bike_reports.db") -> list[dict]:
    priority_order = ["Ташкент", "Самарканд", "Фергана", "Андижан", "Коканд", "Наманган"]
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cities")
        cities = [dict(r) for r in cursor.fetchall()]

    def sort_key(c):
        name = c["name"].strip()
        if name in priority_order:
            return (0, priority_order.index(name))
        return (1, name)

    return sorted(cities, key=sort_key)

def get_city_by_name(name: str, db_path="bike_reports.db") -> dict | None:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cities WHERE name = ?", (name.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- Users & Access Management ---
def authorize_user(user_id: int, username: str = "", full_name: str = "", role: str = "partner", assigned_city: str = "", db_path="bike_reports.db") -> dict:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
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
        cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_user(user_id: int, db_path="bike_reports.db") -> dict | None:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_users(db_path="bike_reports.db") -> list[dict]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
        return [dict(r) for r in cursor.fetchall()]

def is_user_authorized(user_id: int, username: str = None, admin_ids: list = None, db_path="bike_reports.db") -> bool:
    # 1. Admins are ALWAYS authorized
    if is_user_admin(user_id, username, admin_ids, db_path):
        return True

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # 2. If no partners are explicitly added to the whitelist, allow by default
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'partner'")
        partner_count = cursor.fetchone()["cnt"]
        if partner_count == 0:
            return True

        # 3. Otherwise, check if user is in table and active
        cursor.execute("SELECT is_active FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row and row["is_active"] == 1)


def is_user_admin(user_id: int, username: str = None, admin_ids: list = None, db_path="bike_reports.db") -> bool:
    if admin_ids:
        str_uid = str(user_id)
        str_uname = f"@{username}" if username else ""
        for a in admin_ids:
            clean_a = str(a).strip()
            if clean_a and (clean_a == str_uid or (clean_a.startswith("@") and clean_a.lower() == str_uname.lower())):
                return True

    user = get_user(user_id, db_path=db_path)
    if user:
        return bool(user.get("role") == "admin" and user.get("is_active") == 1)

    # Default: if no admins in users table and no ADMIN_IDS set, first unknown user can access admin until explicit admins added
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'admin' AND is_active = 1")
        admin_count = cursor.fetchone()["cnt"]
        if admin_count == 0 and not admin_ids:
            return True

    return False

# --- Bike Reports ---
def add_bike_report(report_data: dict, db_path="bike_reports.db") -> dict:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
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
            report_data.get("created_at")
        ))
        conn.commit()
        report_id = cursor.lastrowid
        res = dict(report_data)
        res["id"] = report_id
        return res

def get_bike_reports(city: str = None, limit: int = 50, db_path="bike_reports.db") -> list[dict]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if city:
            cursor.execute("SELECT * FROM bike_reports WHERE city = ? ORDER BY id DESC LIMIT ?", (city, limit))
        else:
            cursor.execute("SELECT * FROM bike_reports ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
