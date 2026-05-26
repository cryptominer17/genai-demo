"""
smoke_test_auth.py — End-to-end smoke tests for the auth + RBAC system.

No pytest dependency; plain Python.  Exits with code 0 on full pass, 1 on any failure.

Usage
-----
    python scripts/smoke_test_auth.py
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bcrypt
import shared.user_db as user_db

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

_PASS = 0
_FAIL = 0
_TEST_USERNAME = "_smoke_test_user_"
_TEST_EMAIL = "_smoke@test.internal_"


def run(label: str, fn):
    global _PASS, _FAIL
    try:
        fn()
        print(f"  PASS  {label}")
        _PASS += 1
    except Exception as exc:
        print(f"  FAIL  {label}")
        print(f"        {exc}")
        traceback.print_exc(limit=3, file=sys.stdout)
        _FAIL += 1


def assert_true(condition, msg="assertion failed"):
    if not condition:
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------

def cleanup():
    try:
        user_db.delete_user(_TEST_USERNAME)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_init_db():
    user_db.init_db()


def test_default_admin_exists():
    user = user_db.get_user_by_username("admin")
    assert_true(user is not None, "admin user not found")
    assert_true(user["role"] == "admin", f"expected role=admin, got {user['role']}")
    ok = bcrypt.checkpw(b"Admin@123", user["password_hash"].encode())
    assert_true(ok, "password 'Admin@123' did not verify against stored hash")


def test_create_and_list_user():
    cleanup()  # in case a prior run left debris
    user_db.create_user(_TEST_USERNAME, _TEST_EMAIL, "TestPass@1", role="viewer")
    users = user_db.list_users()
    usernames = [u["username"] for u in users]
    assert_true(_TEST_USERNAME in usernames, f"{_TEST_USERNAME} not found in list_users()")


def test_admin_can_access_admin():
    result = user_db.check_app_permission("admin", "admin")
    assert_true(result is True, "admin should have access to 'admin' app")


def test_viewer_cannot_access_data_qa():
    result = user_db.check_app_permission("viewer", "data_qa")
    assert_true(result is False, "viewer should NOT have access to 'data_qa'")


def test_analyst_can_access_data_qa():
    result = user_db.check_app_permission("analyst", "data_qa")
    assert_true(result is True, "analyst should have access to 'data_qa'")


def test_update_password():
    user_db.update_password(_TEST_USERNAME, "NewPass@99")
    user = user_db.get_user_by_username(_TEST_USERNAME)
    assert_true(user is not None, f"{_TEST_USERNAME} not found after update_password()")
    ok = bcrypt.checkpw(b"NewPass@99", user["password_hash"].encode())
    assert_true(ok, "updated password hash does not verify")
    old_ok = bcrypt.checkpw(b"TestPass@1", user["password_hash"].encode())
    assert_true(not old_ok, "old password should no longer verify after update")


def test_toggle_user_active():
    user_before = user_db.get_user_by_username(_TEST_USERNAME)
    assert_true(user_before is not None)
    was_active = user_before["is_active"]
    user_db.toggle_user_active(_TEST_USERNAME)
    user_after = user_db.get_user_by_username(_TEST_USERNAME)
    assert_true(user_after["is_active"] != was_active, "is_active did not flip")
    # Restore
    user_db.toggle_user_active(_TEST_USERNAME)


def test_delete_user():
    user_db.delete_user(_TEST_USERNAME)
    user = user_db.get_user_by_username(_TEST_USERNAME)
    assert_true(user is None, f"{_TEST_USERNAME} still present after delete_user()")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n-- Smoke Test: Auth + RBAC ------------------------------------------")
    print("  Initialising ...\n")

    user_db.init_db()

    tests = [
        ("a. init_db() runs without error",                   test_init_db),
        ("b. Default admin exists, 'Admin@123' verifies",     test_default_admin_exists),
        ("c. create_user() / list_users() round-trip",        test_create_and_list_user),
        ("d. check_app_permission('admin', 'admin') -> True",  test_admin_can_access_admin),
        ("e. check_app_permission('viewer', 'data_qa') -> False", test_viewer_cannot_access_data_qa),
        ("f. check_app_permission('analyst', 'data_qa') -> True", test_analyst_can_access_data_qa),
        ("g. update_password() changes the hash",             test_update_password),
        ("h. toggle_user_active() flips the flag",            test_toggle_user_active),
        ("i. delete_user() removes the test user",            test_delete_user),
    ]

    for label, fn in tests:
        run(label, fn)

    cleanup()  # belt-and-braces final cleanup

    print("\n---------------------------------------------------------------------")
    total = _PASS + _FAIL
    print(f"  Result : {_PASS}/{total} passed", end="")
    if _FAIL:
        print(f"  ({_FAIL} FAILED)")
        sys.exit(1)
    else:
        print("  - all green")
        sys.exit(0)


if __name__ == "__main__":
    main()
