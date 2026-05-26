"""
user_db.py — SQLite-based user management for the PoC Platform.

Provides CRUD operations for users and a role/app permission matrix.
The database is created and seeded automatically on first import.

Usage:
    from shared.user_db import get_user_by_username, check_app_permission
"""

import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

# ---------------------------------------------------------------------------
# Database location
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent / "users.db"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables and seed default data if the database is empty."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'viewer',
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT,
                last_login    TEXT
            );

            CREATE TABLE IF NOT EXISTS app_permissions (
                id         INTEGER PRIMARY KEY,
                role       TEXT NOT NULL,
                app_name   TEXT NOT NULL,
                can_access INTEGER DEFAULT 1,
                UNIQUE(role, app_name)
            );
        """)

        # Seed only when the tables are empty
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                ("admin", "admin@fidelity-demo.com", _hash_password("Admin@123"), "admin", _now()),
            )

        perm_count = conn.execute("SELECT COUNT(*) FROM app_permissions").fetchone()[0]
        if perm_count == 0:
            seed_perms = [
                ("admin",   "document_intelligence", 1),
                ("admin",   "data_qa",               1),
                ("admin",   "report_generator",      1),
                ("admin",   "admin",                 1),
                ("analyst", "document_intelligence", 0),
                ("analyst", "data_qa",               1),
                ("analyst", "report_generator",      1),
                ("analyst", "admin",                 0),
                ("viewer",  "document_intelligence", 1),
                ("viewer",  "data_qa",               0),
                ("viewer",  "report_generator",      0),
                ("viewer",  "admin",                 0),
            ]
            conn.executemany(
                "INSERT INTO app_permissions (role, app_name, can_access) VALUES (?, ?, ?)",
                seed_perms,
            )


def create_user(username: str, email: str, password: str, role: str = "viewer") -> dict:
    """
    Create a new user with a bcrypt-hashed password.

    Parameters
    ----------
    username : str
    email    : str
    password : str  Plain-text password; stored as a bcrypt hash.
    role     : str  One of 'admin', 'analyst', 'viewer'.

    Returns
    -------
    dict  The newly created user record (without password_hash).

    Raises
    ------
    ValueError  If username or email already exists.
    """
    hashed = _hash_password(password)
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users (username, email, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (username, email, hashed, role, _now()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Duplicate username or email: {exc}") from exc

    return get_user_by_username(username)


def get_user_by_username(username: str) -> dict | None:
    """Return a user dict for *username*, or None if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return _row_to_dict(row)


def get_user_by_email(email: str) -> dict | None:
    """Return a user dict for *email*, or None if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    return _row_to_dict(row)


def update_password(username: str, new_password: str) -> None:
    """Replace the stored password hash for *username*."""
    hashed = _hash_password(new_password)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (hashed, username),
        )


def list_users() -> list[dict]:
    """
    Return all users as a list of dicts.

    The ``password_hash`` field is excluded from every record.
    """
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, email, role, is_active, created_at, last_login
            FROM users
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def toggle_user_active(username: str) -> None:
    """Flip the ``is_active`` flag for *username* (1 → 0, 0 → 1)."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET is_active = 1 - is_active WHERE username = ?",
            (username,),
        )


def delete_user(username: str) -> None:
    """Permanently remove *username* from the database."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))


def update_user_role(username: str, new_role: str) -> None:
    """Set the role for *username* to *new_role*."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (new_role, username),
        )


def check_app_permission(role: str, app_name: str) -> bool:
    """
    Return True if *role* is allowed to access *app_name*.

    Defaults to False when no explicit permission record exists.
    """
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT can_access FROM app_permissions WHERE role = ? AND app_name = ?",
            (role, app_name),
        ).fetchone()
    return bool(row["can_access"]) if row else False


def set_app_permission(role: str, app_name: str, can_access: bool) -> None:
    """
    Insert or update the permission for (*role*, *app_name*).

    Parameters
    ----------
    role       : str
    app_name   : str
    can_access : bool
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO app_permissions (role, app_name, can_access)
            VALUES (?, ?, ?)
            ON CONFLICT(role, app_name) DO UPDATE SET can_access = excluded.can_access
            """,
            (role, app_name, int(can_access)),
        )


def get_permissions_matrix() -> dict[str, dict[str, bool]]:
    """
    Return the full permission matrix as a nested dict.

    Example::

        {
            "admin":   {"document_intelligence": True, "data_qa": True, ...},
            "analyst": {...},
            "viewer":  {...},
        }
    """
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, app_name, can_access FROM app_permissions ORDER BY role, app_name"
        ).fetchall()

    matrix: dict[str, dict[str, bool]] = {}
    for row in rows:
        matrix.setdefault(row["role"], {})[row["app_name"]] = bool(row["can_access"])
    return matrix


def record_login(username: str) -> None:
    """Update ``last_login`` to the current UTC timestamp for *username*."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (_now(), username),
        )


# ---------------------------------------------------------------------------
# Auto-initialise on import
# ---------------------------------------------------------------------------

init_db()
