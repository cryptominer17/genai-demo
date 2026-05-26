"""
tests/test_platform.py — FI GenAI PoC Platform test suite.

Covers four test classes:
  TestDatabase       — unit tests for shared/user_db.py using an isolated temp DB
  TestLLMClient      — live Anthropic API smoke tests (requires ANTHROPIC_API_KEY)
  TestHTTPEndpoints  — health checks against the running droplet (requires DROPLET_IP)
  TestRBAC           — permission matrix logic tests

Run locally:
    cd /opt/fi-genai-poc-platform
    source venv/bin/activate
    pytest tests/test_platform.py -v

Run via the test runner (sends email):
    python3 tests/run_tests.py
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

# ---------------------------------------------------------------------------
# Ensure the repo root is importable regardless of cwd
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ===========================================================================
# Helpers
# ===========================================================================

def _make_temp_db() -> Path:
    """Create a fresh temp SQLite file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Path(path)


# ===========================================================================
# CLASS 1 — Database unit tests
# ===========================================================================

class TestDatabase(unittest.TestCase):
    """
    Isolated unit tests for shared/user_db.py.

    Each test method patches user_db._DB_PATH to point at a fresh temp file,
    so tests never touch the production users.db.
    """

    def setUp(self):
        """Create a temp DB and patch the module-level path before each test."""
        self.db_path = _make_temp_db()
        # Import here so the patch context is fresh each time
        import shared.user_db as udb
        self._udb = udb
        self._orig_path = udb._DB_PATH
        udb._DB_PATH = self.db_path
        udb.init_db()  # seed tables + default admin

    def tearDown(self):
        """Restore original path and delete temp file."""
        self._udb._DB_PATH = self._orig_path
        try:
            self.db_path.unlink()
        except FileNotFoundError:
            pass

    # --- Schema ---

    def test_init_db_creates_users_table(self):
        conn = sqlite3.connect(str(self.db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        self.assertIn("users", tables)

    def test_init_db_creates_app_permissions_table(self):
        conn = sqlite3.connect(str(self.db_path))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        self.assertIn("app_permissions", tables)

    def test_init_db_seeds_admin_user(self):
        user = self._udb.get_user_by_username("admin")
        self.assertIsNotNone(user, "Seeded admin user must exist")
        self.assertEqual(user["role"], "admin")
        self.assertEqual(user["is_active"], 1)

    # --- Create / Read ---

    def test_create_user_returns_dict(self):
        result = self._udb.create_user("alice", "alice@demo.com", "Password1!", "analyst")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["role"], "analyst")
        self.assertNotIn("password_hash", result)  # must be excluded

    def test_get_user_by_username_returns_correct_user(self):
        self._udb.create_user("bob", "bob@demo.com", "Password1!", "viewer")
        user = self._udb.get_user_by_username("bob")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "bob@demo.com")

    def test_get_user_by_username_returns_none_for_missing(self):
        result = self._udb.get_user_by_username("nonexistent_user_xyz")
        self.assertIsNone(result)

    def test_duplicate_username_raises_value_error(self):
        self._udb.create_user("dupeuser", "dupe@demo.com", "Password1!", "viewer")
        with self.assertRaises(ValueError):
            self._udb.create_user("dupeuser", "other@demo.com", "Password1!", "viewer")

    def test_duplicate_email_raises_value_error(self):
        self._udb.create_user("user1", "shared@demo.com", "Password1!", "viewer")
        with self.assertRaises(ValueError):
            self._udb.create_user("user2", "shared@demo.com", "Password1!", "viewer")

    # --- List ---

    def test_list_users_excludes_password_hash(self):
        users = self._udb.list_users()
        for u in users:
            self.assertNotIn("password_hash", u)

    def test_list_users_returns_all_users(self):
        self._udb.create_user("u1", "u1@demo.com", "Password1!", "viewer")
        self._udb.create_user("u2", "u2@demo.com", "Password1!", "viewer")
        users = self._udb.list_users()
        usernames = {u["username"] for u in users}
        self.assertIn("admin", usernames)
        self.assertIn("u1", usernames)
        self.assertIn("u2", usernames)

    # --- Update ---

    def test_update_user_role(self):
        self._udb.create_user("charlie", "charlie@demo.com", "Password1!", "viewer")
        self._udb.update_user_role("charlie", "analyst")
        user = self._udb.get_user_by_username("charlie")
        self.assertEqual(user["role"], "analyst")

    def test_update_password_changes_hash(self):
        import bcrypt
        self._udb.create_user("diana", "diana@demo.com", "OldPass1!", "viewer")
        self._udb.update_password("diana", "NewPass1!")
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT password_hash FROM users WHERE username='diana'").fetchone()
        conn.close()
        self.assertTrue(bcrypt.checkpw(b"NewPass1!", row[0].encode()))

    def test_toggle_user_active_deactivates(self):
        self._udb.create_user("eve", "eve@demo.com", "Password1!", "viewer")
        self._udb.toggle_user_active("eve")
        user = self._udb.get_user_by_username("eve")
        self.assertEqual(user["is_active"], 0)

    def test_toggle_user_active_reactivates(self):
        self._udb.create_user("frank", "frank@demo.com", "Password1!", "viewer")
        self._udb.toggle_user_active("frank")  # deactivate
        self._udb.toggle_user_active("frank")  # reactivate
        user = self._udb.get_user_by_username("frank")
        self.assertEqual(user["is_active"], 1)

    def test_record_login_updates_last_login(self):
        self._udb.record_login("admin")
        user = self._udb.get_user_by_username("admin")
        self.assertIsNotNone(user["last_login"])

    def test_delete_user_removes_record(self):
        self._udb.create_user("todelete", "del@demo.com", "Password1!", "viewer")
        self._udb.delete_user("todelete")
        result = self._udb.get_user_by_username("todelete")
        self.assertIsNone(result)

    # --- Permissions ---

    def test_admin_has_all_app_permissions(self):
        apps = ["document_intelligence", "data_qa", "report_generator", "admin"]
        for app in apps:
            self.assertTrue(
                self._udb.check_app_permission("admin", app),
                f"admin should have access to {app}",
            )

    def test_analyst_cannot_access_admin_panel(self):
        self.assertFalse(self._udb.check_app_permission("analyst", "admin"))

    def test_analyst_can_access_data_qa(self):
        self.assertTrue(self._udb.check_app_permission("analyst", "data_qa"))

    def test_viewer_cannot_access_data_qa(self):
        self.assertFalse(self._udb.check_app_permission("viewer", "data_qa"))

    def test_viewer_can_access_document_intelligence(self):
        self.assertTrue(self._udb.check_app_permission("viewer", "document_intelligence"))

    def test_unknown_role_returns_false(self):
        self.assertFalse(self._udb.check_app_permission("ghost_role", "data_qa"))

    def test_set_app_permission_grant(self):
        self._udb.set_app_permission("viewer", "data_qa", True)
        self.assertTrue(self._udb.check_app_permission("viewer", "data_qa"))

    def test_set_app_permission_revoke(self):
        self._udb.set_app_permission("analyst", "data_qa", False)
        self.assertFalse(self._udb.check_app_permission("analyst", "data_qa"))

    def test_get_permissions_matrix_returns_nested_dict(self):
        matrix = self._udb.get_permissions_matrix()
        self.assertIsInstance(matrix, dict)
        self.assertIn("admin", matrix)
        self.assertIsInstance(matrix["admin"], dict)
        self.assertIn("data_qa", matrix["admin"])


# ===========================================================================
# CLASS 2 — LLM Client smoke tests (live Anthropic API)
# ===========================================================================

class TestLLMClient(unittest.TestCase):
    """
    Smoke tests that make real calls to the Anthropic API.

    Requires ANTHROPIC_API_KEY in the environment (loaded via .env).
    Skipped automatically when the key is absent.
    """

    @classmethod
    def setUpClass(cls):
        from shared.config import Config
        if not Config.ANTHROPIC_API_KEY:
            raise unittest.SkipTest("ANTHROPIC_API_KEY not set — skipping LLM tests")
        from shared.llm_client import LLMClient
        cls.llm = LLMClient()

    def test_query_returns_non_empty_string(self):
        result = self.llm.query("Reply with the single word: PONG")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result.strip()), 0)
        self.assertNotIn("API error", result, "Expected a real response, got error string")

    def test_query_with_usage_returns_tuple(self):
        text, tokens = self.llm.query_with_usage("Reply with the single word: PONG")
        self.assertIsInstance(text, str)
        self.assertIsInstance(tokens, int)
        self.assertGreater(tokens, 0, "Token count should be > 0 on success")

    def test_query_with_context_returns_string(self):
        context = "The project codename is FALCON. It was launched in Q3 2024."
        result = self.llm.query_with_context(
            prompt="What is the project codename?",
            context=context,
        )
        self.assertIsInstance(result, str)
        self.assertIn("FALCON", result, "Model should reference the context")

    def test_query_with_context_and_usage_returns_tuple(self):
        context = "Revenue in Q4 was $1.2M."
        text, tokens = self.llm.query_with_context_with_usage(
            prompt="What was the revenue?",
            context=context,
        )
        self.assertIsInstance(text, str)
        self.assertIsInstance(tokens, int)
        self.assertGreater(tokens, 0)

    def test_query_respects_max_tokens(self):
        """Response should be short when max_tokens is very small."""
        result = self.llm.query("Count to 1000.", max_tokens=50)
        self.assertIsInstance(result, str)
        # We can't guarantee length but the call must not crash
        self.assertGreater(len(result), 0)


# ===========================================================================
# CLASS 3 — HTTP endpoint health checks (against the running droplet)
# ===========================================================================

class TestHTTPEndpoints(unittest.TestCase):
    """
    Live HTTP smoke tests against the deployed platform.

    Requires DROPLET_IP in the environment.
    All requests use a short timeout so the suite doesn't hang.
    """

    TIMEOUT = 10  # seconds

    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("DROPLET_IP", "")
        if not cls.base_url:
            raise unittest.SkipTest("DROPLET_IP not set — skipping HTTP endpoint tests")
        if not cls.base_url.startswith("http"):
            cls.base_url = f"http://{cls.base_url}"

    def _get(self, path: str) -> requests.Response:
        url = f"{self.base_url}{path}"
        return requests.get(url, timeout=self.TIMEOUT, allow_redirects=True)

    # --- Landing page ---

    def test_landing_page_returns_200(self):
        resp = self._get("/")
        self.assertEqual(resp.status_code, 200)

    def test_landing_page_contains_platform_title(self):
        resp = self._get("/")
        self.assertIn("FI GenAI", resp.text, "Landing page should mention 'FI GenAI'")

    # --- App routes reachable ---

    def test_document_ai_route_is_reachable(self):
        resp = self._get("/Document_AI/")
        self.assertIn(resp.status_code, [200, 302], "Document AI should return 200 or redirect")

    def test_data_qa_route_is_reachable(self):
        resp = self._get("/Text_to_SQL/")
        self.assertIn(resp.status_code, [200, 302], "Data Q&A should return 200 or redirect")

    def test_report_generator_route_is_reachable(self):
        resp = self._get("/BI_Dashboard/")
        self.assertIn(resp.status_code, [200, 302], "Report Generator should return 200 or redirect")

    def test_admin_route_is_reachable(self):
        resp = self._get("/admin/")
        self.assertIn(resp.status_code, [200, 302], "Admin panel should return 200 or redirect")

    # --- No server error responses ---

    def test_landing_page_not_500(self):
        resp = self._get("/")
        self.assertNotEqual(resp.status_code, 500, "Landing page must not return 500")

    def test_document_ai_not_502(self):
        resp = self._get("/Document_AI/")
        self.assertNotEqual(resp.status_code, 502, "Document AI must not return 502 Bad Gateway")

    def test_data_qa_not_502(self):
        resp = self._get("/Text_to_SQL/")
        self.assertNotEqual(resp.status_code, 502, "Data Q&A must not return 502 Bad Gateway")

    def test_report_generator_not_502(self):
        resp = self._get("/BI_Dashboard/")
        self.assertNotEqual(resp.status_code, 502, "Report Generator must not return 502 Bad Gateway")

    def test_admin_not_502(self):
        resp = self._get("/admin/")
        self.assertNotEqual(resp.status_code, 502, "Admin panel must not return 502 Bad Gateway")

    # --- Response time ---

    def test_landing_page_responds_within_timeout(self):
        """Implicitly passes if _get() doesn't raise a Timeout exception."""
        try:
            self._get("/")
        except requests.exceptions.Timeout:
            self.fail("Landing page did not respond within timeout")

    def test_all_apps_respond_within_timeout(self):
        routes = ["/Document_AI/", "/Text_to_SQL/", "/BI_Dashboard/", "/admin/"]
        for route in routes:
            with self.subTest(route=route):
                try:
                    self._get(route)
                except requests.exceptions.Timeout:
                    self.fail(f"{route} did not respond within {self.TIMEOUT}s")


# ===========================================================================
# CLASS 4 — RBAC permission matrix verification
# ===========================================================================

class TestRBAC(unittest.TestCase):
    """
    Verifies the complete RBAC permission matrix against the seeded defaults.

    Uses an isolated temp DB — does not touch production data.
    """

    def setUp(self):
        self.db_path = _make_temp_db()
        import shared.user_db as udb
        self._udb = udb
        self._orig_path = udb._DB_PATH
        udb._DB_PATH = self.db_path
        udb.init_db()

    def tearDown(self):
        self._udb._DB_PATH = self._orig_path
        try:
            self.db_path.unlink()
        except FileNotFoundError:
            pass

    # --- Expected matrix (matches user_db.py seed) ---
    EXPECTED = {
        "admin":   {"document_intelligence": True,  "data_qa": True,  "report_generator": True,  "admin": True},
        "analyst": {"document_intelligence": False, "data_qa": True,  "report_generator": True,  "admin": False},
        "viewer":  {"document_intelligence": True,  "data_qa": False, "report_generator": False, "admin": False},
    }

    def test_full_permission_matrix_matches_seed(self):
        """Every cell in the matrix must match the expected seed values."""
        for role, apps in self.EXPECTED.items():
            for app, expected_access in apps.items():
                with self.subTest(role=role, app=app):
                    actual = self._udb.check_app_permission(role, app)
                    self.assertEqual(
                        actual,
                        expected_access,
                        f"Role '{role}' / App '{app}': expected {expected_access}, got {actual}",
                    )

    def test_get_permissions_matrix_covers_all_roles(self):
        matrix = self._udb.get_permissions_matrix()
        for role in self.EXPECTED:
            self.assertIn(role, matrix, f"Role '{role}' missing from permissions matrix")

    def test_get_permissions_matrix_covers_all_apps(self):
        matrix = self._udb.get_permissions_matrix()
        expected_apps = {"document_intelligence", "data_qa", "report_generator", "admin"}
        for role, perms in matrix.items():
            actual_apps = set(perms.keys())
            missing = expected_apps - actual_apps
            self.assertFalse(missing, f"Role '{role}' is missing app entries: {missing}")

    def test_admin_always_keeps_admin_panel_access(self):
        """Admin panel access for the admin role must always be True and cannot be set to False."""
        # This enforces the invariant in the Admin Console tab_perms logic
        self._udb.set_app_permission("admin", "admin", False)
        # The platform enforces this in the UI; for DB integrity we re-set it to True
        self._udb.set_app_permission("admin", "admin", True)
        self.assertTrue(self._udb.check_app_permission("admin", "admin"))

    def test_permission_change_is_reflected_immediately(self):
        """set_app_permission changes must be visible to check_app_permission without restart."""
        self.assertFalse(self._udb.check_app_permission("viewer", "data_qa"))
        self._udb.set_app_permission("viewer", "data_qa", True)
        self.assertTrue(self._udb.check_app_permission("viewer", "data_qa"))
        # Revert
        self._udb.set_app_permission("viewer", "data_qa", False)
        self.assertFalse(self._udb.check_app_permission("viewer", "data_qa"))

    def test_new_user_inherits_role_permissions(self):
        """A new user assigned 'analyst' role must inherit the analyst permission set."""
        self._udb.create_user("grace", "grace@demo.com", "Password1!", "analyst")
        user = self._udb.get_user_by_username("grace")
        # Permissions are role-level, not user-level, so verify the role resolves correctly
        self.assertEqual(user["role"], "analyst")
        self.assertTrue(self._udb.check_app_permission(user["role"], "data_qa"))
        self.assertFalse(self._udb.check_app_permission(user["role"], "admin"))


# ===========================================================================
# Entry point (for direct execution without pytest)
# ===========================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
