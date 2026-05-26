"""
user_db.py — SQLite-based user management for the PoC Platform.

Provides CRUD operations for users and a role/app permission matrix.
The database is created and seeded automatically on first import.

Usage:
    from shared.user_db import get_user_by_username, check_app_permission
"""

import sqlite3
from datetime import date, datetime, timedelta, timezone
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
                id                   INTEGER PRIMARY KEY,
                username             TEXT UNIQUE NOT NULL,
                email                TEXT UNIQUE NOT NULL,
                password_hash        TEXT NOT NULL,
                role                 TEXT NOT NULL DEFAULT 'viewer',
                is_active            INTEGER DEFAULT 1,
                created_at           TEXT,
                last_login           TEXT,
                must_change_password INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS app_permissions (
                id         INTEGER PRIMARY KEY,
                role       TEXT NOT NULL,
                app_name   TEXT NOT NULL,
                can_access INTEGER DEFAULT 1,
                UNIQUE(role, app_name)
            );

            CREATE TABLE IF NOT EXISTS usage_log (
                id            INTEGER PRIMARY KEY,
                username      TEXT NOT NULL,
                app_name      TEXT NOT NULL,
                request_count INTEGER DEFAULT 1,
                token_count   INTEGER DEFAULT 0,
                logged_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_app_overrides (
                id         INTEGER PRIMARY KEY,
                username   TEXT NOT NULL,
                app_name   TEXT NOT NULL,
                can_access INTEGER DEFAULT 1,
                granted_by TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                UNIQUE(username, app_name)
            );
        """)

        # Migrate: add must_change_password to users if upgrading from an older schema.
        try:
            conn.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Seed only when the tables are empty
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count == 0:
            conn.execute(
                """
                INSERT INTO users
                    (username, email, password_hash, role, is_active,
                     created_at, must_change_password)
                VALUES (?, ?, ?, ?, 1, ?, 1)
                """,
                (
                    "admin",
                    "admin@fidelity-demo.com",
                    _hash_password("Admin@123"),
                    "admin",
                    _now(),
                ),
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

    Notes
    -----
    New users are always created with ``must_change_password=1`` so they are
    required to set a personal password on first login.
    """
    hashed = _hash_password(password)
    try:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO users
                    (username, email, password_hash, role, is_active,
                     created_at, must_change_password)
                VALUES (?, ?, ?, ?, 1, ?, 1)
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


def set_must_change_password(username: str, value: bool) -> None:
    """Set or clear the must_change_password flag for *username*."""
    with _get_conn() as conn:
        conn.execute(
            "UPDATE users SET must_change_password = ? WHERE username = ?",
            (int(value), username),
        )


def list_users() -> list[dict]:
    """
    Return all users as a list of dicts.

    The ``password_hash`` field is excluded from every record.
    """
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, email, role, is_active, created_at, last_login,
                   must_change_password
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


def check_app_permission(role: str, app_name: str, username: str = None) -> bool:
    """
    Return True if the user is allowed to access *app_name*.

    Checks user-level overrides first; falls back to the role-based
    permission matrix when no override exists for *username*.

    Parameters
    ----------
    role     : str
    app_name : str
    username : str, optional
        When provided, user-level overrides are evaluated before the role matrix.
    """
    # 1. User-level override takes highest priority.
    if username:
        with _get_conn() as conn:
            override = conn.execute(
                "SELECT can_access FROM user_app_overrides"
                " WHERE username = ? AND app_name = ?",
                (username, app_name),
            ).fetchone()
        if override is not None:
            return bool(override["can_access"])

    # 2. Fall back to the role-based permission matrix.
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
# Usage tracking
# ---------------------------------------------------------------------------

def record_usage(username: str, app_name: str, tokens_used: int) -> None:
    """
    Insert one usage record into usage_log.

    Each call represents a single LLM request. ``request_count`` is always
    1 per row; callers aggregate with SUM() via get_usage_summary().

    Parameters
    ----------
    username   : str
    app_name   : str  One of the known app identifiers.
    tokens_used: int  Total tokens consumed (input + output).
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO usage_log (username, app_name, request_count, token_count, logged_at)
            VALUES (?, ?, 1, ?, ?)
            """,
            (username, app_name, tokens_used, _now()),
        )


def get_usage_by_user(username: str) -> list[dict]:
    """Return all usage records for *username*, newest first."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, app_name, request_count, token_count, logged_at
            FROM usage_log
            WHERE username = ?
            ORDER BY logged_at DESC
            """,
            (username,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_usage_summary(date_from: str = None, date_to: str = None) -> list[dict]:
    """
    Return aggregated usage grouped by (username, app_name).

    Parameters
    ----------
    date_from : str, optional  ISO date string ``YYYY-MM-DD``. Inclusive lower bound.
    date_to   : str, optional  ISO date string ``YYYY-MM-DD``. Inclusive upper bound
                               (the full calendar day is included).

    Returns
    -------
    list[dict]
        Each dict has keys: username, app_name, total_requests, total_tokens.
    """
    conditions: list[str] = []
    params: list = []

    if date_from:
        conditions.append("logged_at >= ?")
        params.append(date_from)
    if date_to:
        # Shift end by one day so the full final calendar day is included.
        end = (date.fromisoformat(date_to) + timedelta(days=1)).isoformat()
        conditions.append("logged_at < ?")
        params.append(end)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT username,
               app_name,
               SUM(request_count) AS total_requests,
               SUM(token_count)   AS total_tokens
        FROM usage_log
        {where}
        GROUP BY username, app_name
        ORDER BY username, app_name
    """

    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Per-user app access overrides
# ---------------------------------------------------------------------------

def set_user_override(
    username: str, app_name: str, can_access: bool, granted_by: str
) -> None:
    """
    Insert or update a per-user access override for (*username*, *app_name*).

    Overrides take precedence over role-based permissions in check_app_permission().

    Parameters
    ----------
    username   : str
    app_name   : str
    can_access : bool
    granted_by : str  Username of the admin recording the change.
    """
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_app_overrides
                (username, app_name, can_access, granted_by, granted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(username, app_name) DO UPDATE SET
                can_access = excluded.can_access,
                granted_by = excluded.granted_by,
                granted_at = excluded.granted_at
            """,
            (username, app_name, int(can_access), granted_by, _now()),
        )


def get_user_overrides(username: str) -> list[dict]:
    """Return all app access overrides for *username*."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, app_name, can_access, granted_by, granted_at
            FROM user_app_overrides
            WHERE username = ?
            ORDER BY app_name
            """,
            (username,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_user_overrides() -> list[dict]:
    """Return all per-user overrides across every user."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, app_name, can_access, granted_by, granted_at
            FROM user_app_overrides
            ORDER BY username, app_name
            """
        ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Auto-initialise on import
# ---------------------------------------------------------------------------

init_db()
