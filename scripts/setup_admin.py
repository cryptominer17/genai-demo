"""
setup_admin.py — One-time database initialisation and first-admin creation.

Usage
-----
    python scripts/setup_admin.py
    python scripts/setup_admin.py --username john --email john@example.com --password Secret1!
"""

import argparse
import sys
from pathlib import Path

# Allow running from any cwd: add project root to path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.user_db as user_db


APPS = ["document_intelligence", "data_qa", "report_generator", "admin"]
COL_W = 24


def print_banner(text: str) -> None:
    bar = "=" * (len(text) + 4)
    print(f"\n+{bar}+")
    print(f"|  {text}  |")
    print(f"+{bar}+")


def print_users_table(users: list[dict]) -> None:
    print(f"\n{'ID':<4} {'Username':<16} {'Email':<32} {'Role':<10} {'Active':<8} {'Created'}")
    print("-" * 88)
    for u in users:
        active = "yes" if u["is_active"] else "no"
        created = (u["created_at"] or "")[:19].replace("T", " ")
        print(f"{u['id']:<4} {u['username']:<16} {u['email']:<32} {u['role']:<10} {active:<8} {created}")


def print_access_matrix(matrix: dict) -> None:
    roles = sorted(matrix.keys())
    header = f"\n{'App':<{COL_W}}" + "".join(f"{r:<12}" for r in roles)
    print(header)
    print("-" * (COL_W + 12 * len(roles)))
    for app in APPS:
        row = f"{app:<{COL_W}}"
        for role in roles:
            perms = matrix.get(role, {})
            row += ("YES" if perms.get(app) else "---").ljust(12)
        print(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialise the user database and create the first admin account."
    )
    parser.add_argument("--username", default=None, help="Admin username (default: admin)")
    parser.add_argument("--email", default=None, help="Admin email")
    parser.add_argument("--password", default=None, help="Admin password (default: Admin@123)")
    args = parser.parse_args()

    print_banner("FI GenAI Platform - DB Setup")

    # 1. Initialise tables and seed default data
    print("\n[1/3] Initialising database ...")
    user_db.init_db()
    print(f"      Database path : {user_db._DB_PATH}")
    print("      Tables ready  : users, app_permissions")

    # 2. Optionally create a custom first admin
    if args.username or args.email or args.password:
        username = args.username or "admin"
        email = args.email or f"{username}@fidelity-demo.com"
        password = args.password or "Admin@123"

        existing = user_db.get_user_by_username(username)
        if existing:
            print(f"\n[2/3] User '{username}' already exists - skipping creation.")
        else:
            print(f"\n[2/3] Creating admin user '{username}' ...")
            user_db.create_user(username, email, password, role="admin")
            print(f"      Created : {username} / {email} (role=admin)")
    else:
        # init_db() already seeds the default admin when the table is empty
        users = user_db.list_users()
        if any(u["role"] == "admin" for u in users):
            print("\n[2/3] Default admin already present - no action needed.")
        else:
            print("\n[2/3] No admin found; default admin created by init_db().")

    # 3. Print summary
    print_banner("Current Users")
    users = user_db.list_users()
    print_users_table(users)

    print_banner("Access Matrix")
    matrix = user_db.get_permissions_matrix()
    print_access_matrix(matrix)

    print("\nSetup complete.\n")


if __name__ == "__main__":
    main()
