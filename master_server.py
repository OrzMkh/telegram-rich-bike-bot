import os
import json
import sqlite3
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from config import DB_PATH

logger = logging.getLogger(__name__)

WEB_APP_DIR = os.path.join(os.path.dirname(__file__), "web_app")
TASKS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "telegram-task-manager-bot", "tasks.db")
if not os.path.exists(TASKS_DB_PATH):
    TASKS_DB_PATH = "tasks.db"

class MasterHubHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_APP_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.handle_api_get()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.handle_api_post()
        else:
            self.send_error(404, "Not Found")

    def handle_api_get(self):
        path = self.path.split("?")[0]
        if path == "/api/dashboard":
            data = self.get_dashboard_data()
            self.send_json_response(data)
        elif path == "/api/cities":
            data = self.get_cities_data()
            self.send_json_response(data)
        elif path == "/api/reports":
            data = self.get_reports_data()
            self.send_json_response(data)
        elif path == "/api/tasks":
            data = self.get_tasks_data()
            self.send_json_response(data)
        elif path == "/api/users":
            data = self.get_users_data()
            self.send_json_response(data)
        else:
            self.send_error(404, "API Endpoint Not Found")

    def handle_api_post(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        path = self.path.split("?")[0]
        if path == "/api/cities/update_total":
            city_id = payload.get("city_id")
            total_bikes = payload.get("total_bikes")
            if city_id and total_bikes:
                self.update_city_total(city_id, total_bikes)
                self.send_json_response({"status": "ok"})
            else:
                self.send_json_response({"error": "Invalid params"}, status=400)
        elif path == "/api/users/toggle_access":
            user_id = payload.get("user_id")
            is_active = payload.get("is_active", 1)
            if user_id is not None:
                self.toggle_user_access(user_id, is_active)
                self.send_json_response({"status": "ok"})
            else:
                self.send_json_response({"error": "Invalid params"}, status=400)
        else:
            self.send_error(404, "API Endpoint Not Found")

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def get_dashboard_data(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT SUM(total_bikes) as tot FROM cities")
            row = c.fetchone()
            tot_bikes = row["tot"] if row and row["tot"] else 0

            c.execute("SELECT COUNT(*) as cnt FROM users")
            row_u = c.fetchone()
            tot_users = row_u["cnt"] if row_u else 0
            conn.close()
        except Exception:
            tot_bikes = 0
            tot_users = 0

        # Tasks count
        tot_tasks = 0
        if os.path.exists(TASKS_DB_PATH):
            try:
                conn_t = sqlite3.connect(TASKS_DB_PATH)
                conn_t.row_factory = sqlite3.Row
                ct = conn_t.cursor()
                ct.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'Active'")
                row_t = ct.fetchone()
                tot_tasks = row_t["cnt"] if row_t else 0
                conn_t.close()
            except Exception:
                tot_tasks = 0

        return {
            "total_bikes": tot_bikes,
            "share_on_line": 68,
            "active_tasks": tot_tasks,
            "total_users": tot_users,
        }

    def get_cities_data(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, name, total_bikes, has_bike_types FROM cities ORDER BY id ASC")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to get cities: {e}")
            return []

    def update_city_total(self, city_id: int, total_bikes: int):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE cities SET total_bikes = ? WHERE id = ?", (total_bikes, city_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to update city total: {e}")

    def get_reports_data(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, username, city, report_date, issued, returned, total_in_trip, broken_bikes FROM bike_reports ORDER BY id DESC LIMIT 5")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to get reports: {e}")
            return []

    def get_tasks_data(self):
        if not os.path.exists(TASKS_DB_PATH):
            return []
        try:
            conn = sqlite3.connect(TASKS_DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, task_text, assignee, author, sla_deadline, status FROM tasks ORDER BY id DESC LIMIT 10")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to get tasks: {e}")
            return []

    def get_users_data(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, user_id, username, full_name, role, is_active FROM users ORDER BY id ASC")
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []

    def toggle_user_access(self, user_id: int, is_active: int):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET is_active = ? WHERE user_id = ?", (is_active, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to toggle user access: {e}")

def run_master_server(port=8080):
    server = HTTPServer(("0.0.0.0", port), MasterHubHandler)
    logger.info(f"Master Hub HTTP & API Server running on port {port}.")
    server.serve_forever()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_master_server(8080)
