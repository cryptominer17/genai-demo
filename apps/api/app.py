"""
REST API for the Admin HTML dashboard — runs on port 8505.
Provides user management and usage data endpoints, protected by
session-token auth (admin role required).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import bcrypt
import hashlib
import hmac as _hmac
import secrets
import time
from datetime import date, timedelta
from functools import wraps

from flask import Flask, g, jsonify, request

from shared import user_db

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# In-memory token store — cleared on restart (acceptable for a PoC)
_sessions: dict = {}
_SECRET_KEY = secrets.token_hex(32)
SESSION_TTL = 8 * 3600  # seconds

USER_APPS = ["document_intelligence", "data_qa", "report_generator"]
VALID_ROLES = ("admin", "analyst", "viewer")


def _new_token(username: str) -> str:
    payload = f"{username}:{time.monotonic()}:{secrets.token_hex(8)}"
    return _hmac.new(_SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Unauthorized"}), 401
        token = auth[7:]
        session = _sessions.get(token)
        if not session:
            return jsonify({"error": "Unauthorized"}), 401
        if time.monotonic() > session["expires_at"]:
            _sessions.pop(token, None)
            return jsonify({"error": "Session expired"}), 401
        if session["role"] != "admin":
            return jsonify({"error": "Forbidden"}), 403
        g.session = session
        return f(*args, **kwargs)
    return wrapper


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = user_db.get_user_by_username(username)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.get("is_active"):
        return jsonify({"error": "Account is inactive"}), 403

    try:
        ok = bcrypt.checkpw(password.encode(), user["password_hash"].encode())
    except Exception:
        ok = False

    if not ok:
        return jsonify({"error": "Invalid credentials"}), 401
    if user["role"] != "admin":
        return jsonify({"error": "Admin access required"}), 403

    token = _new_token(username)
    _sessions[token] = {
        "username": username,
        "role": user["role"],
        "expires_at": time.monotonic() + SESSION_TTL,
    }
    user_db.record_login(username)
    return jsonify({"token": token, "username": username})


@app.route("/api/logout", methods=["POST"])
@require_admin
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        _sessions.pop(auth[7:], None)
    return jsonify({"ok": True})


@app.route("/api/stats")
@require_admin
def get_stats():
    users = user_db.list_users()
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    usage = user_db.get_usage_summary(date_from=today, date_to=tomorrow)
    today_requests = sum(int(r.get("total_requests", 0)) for r in usage)
    today_tokens = sum(int(r.get("total_tokens", 0)) for r in usage)
    return jsonify({
        "total_users": len(users),
        "active_users": sum(1 for u in users if u["is_active"]),
        "today_requests": today_requests,
        "today_tokens": today_tokens,
    })


@app.route("/api/users", methods=["GET"])
@require_admin
def get_users():
    users = user_db.list_users()
    result = []
    for u in users:
        app_access = {
            app_name: bool(
                user_db.check_app_permission(u["role"], app_name, username=u["username"])
            )
            for app_name in USER_APPS
        }
        result.append({
            "username": u["username"],
            "email": u["email"],
            "role": u["role"],
            "is_active": bool(u["is_active"]),
            "must_change_password": bool(u.get("must_change_password", 0)),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
            "app_access": app_access,
        })
    return jsonify(result)


@app.route("/api/users", methods=["POST"])
@require_admin
def add_user():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "viewer"))

    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if role not in VALID_ROLES:
        return jsonify({"error": "Invalid role"}), 400

    try:
        created = user_db.create_user(username, email, password, role)
        return jsonify(created), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409


@app.route("/api/users/<username>", methods=["PATCH"])
@require_admin
def update_user(username):
    data = request.get_json(silent=True) or {}

    if "is_active" in data:
        user = user_db.get_user_by_username(username)
        if user and bool(user["is_active"]) != bool(data["is_active"]):
            user_db.toggle_user_active(username)

    if "role" in data:
        new_role = str(data["role"])
        if new_role not in VALID_ROLES:
            return jsonify({"error": "Invalid role"}), 400
        user_db.update_user_role(username, new_role)

    return jsonify({"ok": True})


@app.route("/api/users/<username>", methods=["DELETE"])
@require_admin
def delete_user(username):
    if username == g.session["username"]:
        return jsonify({"error": "Cannot delete your own account"}), 400
    user_db.delete_user(username)
    return jsonify({"ok": True})


@app.route("/api/users/<username>/access", methods=["PATCH"])
@require_admin
def update_access(username):
    data = request.get_json(silent=True) or {}
    app_access = data.get("app_access", {})
    for app_name, can_access in app_access.items():
        if app_name in USER_APPS:
            user_db.set_user_override(
                username, app_name, bool(can_access),
                granted_by=g.session["username"],
            )
    return jsonify({"ok": True})


@app.route("/api/users/<username>/password", methods=["POST"])
@require_admin
def reset_password(username):
    data = request.get_json(silent=True) or {}
    new_password = str(data.get("password", ""))
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    user_db.update_password(username, new_password)
    user_db.set_must_change_password(username, bool(data.get("force_change", True)))
    return jsonify({"ok": True})


@app.route("/api/usage")
@require_admin
def get_usage():
    days = min(int(request.args.get("days", 30)), 365)
    today = date.today()
    date_from = (today - timedelta(days=days)).isoformat()
    date_to = today.isoformat()
    return jsonify(user_db.get_usage_summary(date_from=date_from, date_to=date_to))


if __name__ == "__main__":
    user_db.init_db()
    app.run(host="127.0.0.1", port=8505, debug=False)
