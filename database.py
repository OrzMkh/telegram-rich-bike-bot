import sqlite3
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@contextmanager
def get_connection(db_path="rich_bikes.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db(db_path="rich_bikes.db"):
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rich_bike_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                city TEXT DEFAULT 'Ташкент',
                report_date TEXT NOT NULL,
                issued TEXT NOT NULL,
                returned TEXT NOT NULL,
                total_in_trip TEXT NOT NULL,
                new_bikes TEXT NOT NULL,
                batteries_status TEXT NOT NULL,
                broken_bikes TEXT NOT NULL,
                return_reasons TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

def add_rich_report(report: dict, db_path="rich_bikes.db") -> dict:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rich_bike_reports (
                user_id, username, city, report_date, issued, returned,
                total_in_trip, new_bikes, batteries_status, broken_bikes,
                return_reasons, comment, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.get("user_id"),
            report.get("username", "Партнёр"),
            report.get("city", "Ташкент"),
            report.get("report_date", ""),
            report.get("issued", "0"),
            report.get("returned", "0"),
            report.get("total_in_trip", "0"),
            report.get("new_bikes", "0"),
            report.get("batteries_status", "100%"),
            report.get("broken_bikes", "0"),
            report.get("return_reasons", "—"),
            report.get("comment", "—"),
            report.get("created_at", "")
        ))
        conn.commit()
        report_id = cursor.lastrowid
        res = dict(report)
        res["id"] = report_id
        return res

def get_rich_reports(limit=10, db_path="rich_bikes.db") -> list:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM rich_bike_reports
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
