# GenAI Demo — Admin Panel & RBAC Build Plan
**For exec demo | Repo: cryptominer17/genai-demo | Local: G:\genai-demo**

---

## Part 1 — Current State Review

### What exists
The platform is a 3-app Streamlit PoC (Document Intelligence, Data Q&A, Report Generator) deployed behind Nginx on a DigitalOcean droplet. There is a shared `auth.py` and `config.py` under `shared/`.

### Critical gaps (what is broken or missing)

| Issue | Root Cause | Impact on Demo |
|---|---|---|
| **Single hardcoded credential** | `shared/auth.py` reads one `STREAMLIT_USERNAME` + `STREAMLIT_PASSWORD` from `.env` — no user database | Cannot add users or manage access |
| **No admin panel** | `deploy_ui.py` is a Docker deploy tool, not a user admin UI — there is no admin app in the repo | Nothing to show executives for user governance |
| **Logout unreliable** | `SimpleAuthenticator.logout()` clears session state and calls `st.rerun()` — works in theory but breaks when Streamlit reruns the page before clearing completes in some versions | Embarrassing in a live demo |
| **No RBAC** | All logged-in users see all 3 apps with full access — no role checking, no per-app restrictions | Cannot demonstrate enterprise access control |
| **No user signup / invite** | No mechanism to add new users at runtime — must edit `.env` and restart | Not demo-able |
| **No password reset** | No reset flow of any kind | Gap in user lifecycle story |
| **`bcrypt` already in requirements** | `bcrypt==4.1.2` is present in `shared/requirements.txt` — good, nothing to add for password hashing | Can proceed with secure hashing immediately |

### What is working
- All 3 Streamlit apps run and call Claude correctly once logged in
- LLM client (`shared/llm_client.py`) is clean and functional
- Nginx reverse proxy config is in place
- GitHub Actions CI/CD pipeline exists

---

## Part 2 — Architecture for the Fix

```
shared/
├── auth.py          ← REWRITE: multi-user bcrypt login + role in session
├── user_db.py       ← NEW: SQLite user store (users, roles, app_permissions)
├── config.py        ← no change needed
└── requirements.txt ← no change (bcrypt already present)

apps/
├── admin/
│   └── streamlit_app.py   ← NEW: Admin panel (port 8504, route /Admin)
├── document_intelligence/streamlit_app.py  ← UPDATE: add role gate
├── data_qa/streamlit_app.py               ← UPDATE: add role gate
└── report_generator/streamlit_app.py      ← UPDATE: add role gate

deployment/
└── nginx.conf      ← UPDATE: add /Admin → :8504 route
```

**Roles for demo:**
- `admin` — full access to all apps + Admin panel
- `analyst` — access to Data Q&A + Report Generator
- `viewer` — access to Document Intelligence only

---

## Part 3 — Subagent Prompts (paste each into Claude Code in order)

---

### SUBAGENT 1 — Build the User Database Layer

> **Paste this prompt into Claude Code (Claude in terminal / `claude` CLI)**

```
You are working in the repo at G:\genai-demo (local) / https://github.com/cryptominer17/genai-demo.

TASK: Create shared/user_db.py — a SQLite-based user management module.

REQUIREMENTS:

1. Database file location: repo_root/shared/users.db (create on first import if it doesn't exist).

2. Schema:
   - Table `users`: id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, 
     email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, 
     role TEXT NOT NULL DEFAULT 'viewer', is_active INTEGER DEFAULT 1,
     created_at TEXT, last_login TEXT
   - Table `app_permissions`: id INTEGER PRIMARY KEY, role TEXT NOT NULL, 
     app_name TEXT NOT NULL, can_access INTEGER DEFAULT 1,
     UNIQUE(role, app_name)

3. Functions to implement (all with docstrings):
   - init_db() → creates tables and seeds default data if empty
   - create_user(username, email, password, role) → hashes password with bcrypt, inserts row, returns user dict or raises ValueError on duplicate
   - get_user_by_username(username) → returns user dict or None
   - get_user_by_email(email) → returns user dict or None
   - update_password(username, new_password) → bcrypt hash and update
   - list_users() → returns list of user dicts (no password_hash)
   - toggle_user_active(username) → flip is_active
   - delete_user(username) → hard delete
   - update_user_role(username, new_role) → update role
   - check_app_permission(role, app_name) → returns True/False
   - set_app_permission(role, app_name, can_access) → upsert
   - get_permissions_matrix() → returns dict {role: {app_name: bool}}
   - record_login(username) → update last_login timestamp

4. Seed data on first init:
   - Default admin user: username="admin", email="admin@fidelity-demo.com", 
     password="Admin@123" (bcrypt hashed), role="admin"
   - App permissions matrix:
     - admin: document_intelligence=True, data_qa=True, report_generator=True, admin=True
     - analyst: document_intelligence=False, data_qa=True, report_generator=True, admin=False
     - viewer: document_intelligence=True, data_qa=False, report_generator=False, admin=False

5. Use only stdlib + bcrypt (already in shared/requirements.txt). No SQLAlchemy.

6. The module must call init_db() at import time so no setup step is needed.

After writing the file, run: python -c "from shared.user_db import list_users; print(list_users())" from the repo root to verify.
```

---

### SUBAGENT 2 — Rewrite the Auth Layer

> **Paste this prompt into Claude Code after Subagent 1 completes**

```
You are working in the repo at G:\genai-demo.

CONTEXT: shared/user_db.py now exists with SQLite multi-user management. 
The current shared/auth.py uses a single hardcoded credential from .env — we need to replace it with a proper multi-user system.

TASK: Rewrite shared/auth.py to use the new user_db module.

REQUIREMENTS:

1. Keep the same public API so all 3 existing apps need minimal changes:
   - setup_authenticator() → returns a SimpleAuthenticator instance
   - require_login(authenticator) → returns (name, username) tuple, calls st.stop() if not logged in

2. SimpleAuthenticator class changes:
   - __init__: no arguments needed
   - login(username, password) → verifies against user_db, sets session state keys:
     st.session_state["authenticated"] = True/False
     st.session_state["username"] = username
     st.session_state["name"] = display name (username for now)
     st.session_state["role"] = user's role ("admin", "analyst", "viewer")
   - logout(button_name, location="main", key=None) → same signature, fix the implementation:
     use a unique key per call, explicitly clear all session state keys on click, 
     call st.rerun() — make this bulletproof for demo
   - has_permission(app_name) → checks st.session_state["role"] against user_db.check_app_permission

3. require_login should:
   - Show a clean, styled login form (Fidelity Institutional branding: dark blue header, logo text "FI GenAI Platform")
   - Show "Invalid credentials" on failure (not which field is wrong)
   - Call record_login() from user_db on successful login
   - After login, check if the user's role has permission for the current app 
     (pass app_name as optional param to require_login with default None — if None, skip permission check)

4. Add new helper: require_permission(app_name) — call this at the top of each app after require_login. 
   Shows st.error("You don't have access to this application. Contact your administrator.") 
   and calls st.stop() if permission denied.

5. Remove all references to Config.STREAMLIT_USERNAME and Config.STREAMLIT_PASSWORD (no longer needed for auth).

6. Keep the module importable: do not call st functions at module level.

After writing, do a quick syntax check: python -c "from shared.auth import setup_authenticator, require_login; print('auth ok')"
```

---

### SUBAGENT 3 — Build the Admin Panel App

> **Paste this prompt into Claude Code after Subagent 2 completes**

```
You are working in the repo at G:\genai-demo.

CONTEXT: 
- shared/user_db.py → SQLite user management (users table + app_permissions table)
- shared/auth.py → rewritten multi-user auth with role in session state
- There is NO admin app yet — deploy_ui.py is unrelated (a Docker deploy tool)

TASK: Create apps/admin/streamlit_app.py — a full admin panel for user management and RBAC.

REQUIREMENTS:

1. Page config: title="FI GenAI Admin", icon="🔐", layout="wide"

2. Auth gate at the top:
   from shared.auth import setup_authenticator, require_login, require_permission
   authenticator = setup_authenticator()
   name, username = require_login(authenticator, app_name="admin")
   require_permission("admin")
   (Only admin-role users can access this page)

3. Header: "🔐 FI GenAI Platform — Admin Console" with logout button top-right.
   Show logged-in user's name and role as a small caption.

4. Four tabs: "👥 Users", "🔑 Add User", "🔒 App Permissions", "🔄 Reset Password"

--- TAB 1: Users ---
- Call user_db.list_users() and display as a styled st.dataframe (hide password_hash, show: username, email, role, is_active, created_at, last_login)
- For each user (use st.expander or inline controls): 
  - "Deactivate / Activate" toggle button (calls toggle_user_active)
  - "Change Role" selectbox (admin/analyst/viewer) + Save button (calls update_user_role)
  - "Delete" button with a confirmation checkbox (calls delete_user; cannot delete own account)
- Show total user count metric at top

--- TAB 2: Add User ---
- Form with fields: Username, Email, Role (selectbox: admin/analyst/viewer), 
  Password, Confirm Password
- Validate: username non-empty, email format, passwords match, min 8 chars
- On submit: call user_db.create_user() and show success/error message
- After success, show the new user's credentials in a st.success box

--- TAB 3: App Permissions ---
- Show a permission matrix table: rows = roles (admin, analyst, viewer), 
  columns = app names (document_intelligence, data_qa, report_generator, admin)
- Each cell is a checkbox bound to user_db.get_permissions_matrix()
- "Save Permissions" button at the bottom calls set_app_permission for each changed cell
- Show a note: "admin role always retains admin panel access (cannot be revoked)"
- Refresh button to reload matrix from DB

--- TAB 4: Reset Password ---
- Form: select username from dropdown (call list_users), new password, confirm password
- Admin can reset any user's password without knowing the old one
- Validate passwords match, min 8 chars
- On submit: call user_db.update_password() and show confirmation

5. Style notes:
   - Use st.metric() for summary stats (Total Users, Active Users, Roles count)
   - Use st.success/st.error/st.warning for all feedback
   - No dummy/hardcoded data — everything reads live from user_db

6. Create apps/admin/__init__.py (empty) and apps/admin/requirements.txt referencing ../../shared/requirements.txt (or just list the same deps).

After writing, check syntax: python -c "import ast; ast.parse(open('apps/admin/streamlit_app.py').read()); print('admin app syntax ok')"
```

---

### SUBAGENT 4 — Add RBAC Gates to All Three Apps

> **Paste this prompt into Claude Code after Subagent 3 completes**

```
You are working in the repo at G:\genai-demo.

CONTEXT: 
- shared/auth.py now has require_permission(app_name) function
- App names used in user_db: "document_intelligence", "data_qa", "report_generator"
- All 3 apps already call require_login(authenticator) — we need to add the permission check

TASK: Update all three existing Streamlit apps to enforce RBAC.

CHANGES NEEDED IN EACH APP:

apps/document_intelligence/streamlit_app.py:
1. Change: `name, username = require_login(authenticator)`
   To: `name, username = require_login(authenticator, app_name="document_intelligence")`
2. Add immediately after: `require_permission("document_intelligence")`
3. In the header sidebar, add a small caption showing: 
   f"Logged in as: {username} ({st.session_state.get('role', '')})"

apps/data_qa/streamlit_app.py:
1. Change require_login call to include app_name="data_qa"
2. Add require_permission("data_qa") after
3. Add the same user/role caption in sidebar

apps/report_generator/streamlit_app.py:
1. Change require_login call to include app_name="report_generator"
2. Add require_permission("report_generator") after
3. Add the same user/role caption in sidebar

ALSO in shared/auth.py — update require_login signature:
- Add optional parameter: app_name: str = None
- If app_name is provided and user is already authenticated, immediately check permission 
  and call st.error + st.stop() if denied (so returning users get gated too, not just on first login)

After all edits, verify no import errors:
python -c "import ast; [ast.parse(open(f).read()) for f in ['apps/document_intelligence/streamlit_app.py','apps/data_qa/streamlit_app.py','apps/report_generator/streamlit_app.py']]; print('all apps syntax ok')"
```

---

### SUBAGENT 5 — Fix Logout + Polish UI + Update Nginx

> **Paste this prompt into Claude Code after Subagent 4 completes**

```
You are working in the repo at G:\genai-demo.

TASK: Three polish tasks — fix logout reliability, improve login UI, update Nginx config.

--- PART A: Bulletproof Logout ---

In shared/auth.py, rewrite the logout method to be completely reliable for demo:

def logout(self, button_name: str = "Logout", location: str = "main", key: str = "logout_btn"):
    # Generate a stable unique key if not provided
    _key = key or f"logout_{location}"
    
    if location == "sidebar":
        clicked = st.sidebar.button(button_name, key=_key, type="secondary")
    else:
        clicked = st.button(button_name, key=_key, type="secondary")
    
    if clicked:
        # Clear ALL session state keys related to auth
        for k in ["authenticated", "username", "name", "role"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

--- PART B: Styled Login Form ---

In shared/auth.py, improve the require_login login form UI:
- Add st.markdown with CSS to style the login container (centered, max-width 400px, subtle border, shadow)
- Show "🏦 Fidelity Institutional GenAI Platform" as the header in dark navy (#0A3D6B)  
- Show "Secure access — enter your credentials" as subtitle
- After the login form, add a small footer: "© 2026 Fidelity Institutional | AI Platform Demo"
- Use st.columns to center the form: col1, form_col, col2 = st.columns([1,2,1])

--- PART C: Update Nginx Config ---

In deployment/nginx.conf, add a new location block for the Admin app.
Look at the existing pattern (e.g., /Document_AI → :8501) and add:
    location /Admin {
        proxy_pass http://localhost:8504;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

--- PART D: Create systemd service for Admin app ---

Create deployment/systemd/streamlit-admin.service following the exact same pattern as 
deployment/systemd/streamlit-doc-intelligence.service but with:
- Description=FI GenAI Admin Panel
- ExecStart pointing to apps/admin/streamlit_app.py --server.port 8504
- Same User, WorkingDirectory, Environment, Restart settings

After all changes, show a summary of every file modified.
```

---

### SUBAGENT 6 — Create Setup Script + End-to-End Smoke Test

> **Paste this prompt into Claude Code after Subagent 5 completes**

```
You are working in the repo at G:\genai-demo.

TASK: Create a setup/seed script and run a smoke test of the full auth + RBAC system.

--- PART A: Create scripts/setup_admin.py ---

A one-time setup script that:
1. Calls shared/user_db.init_db() 
2. Checks if any users exist — if not, creates the default admin
3. Prints a summary of users and permissions in the DB
4. Accepts optional CLI args: --username, --email, --password to create a custom first admin
5. Shows the access matrix at the end

Run it as: python scripts/setup_admin.py

--- PART B: Create scripts/smoke_test_auth.py ---

A test script (no pytest, just plain Python) that:
1. Imports shared/user_db and shared/auth (non-Streamlit parts only)
2. Tests:
   a. init_db() runs without error
   b. Default admin user exists and password "Admin@123" verifies correctly with bcrypt
   c. create_user() creates a test user and list_users() returns them
   d. check_app_permission("admin", "admin") returns True
   e. check_app_permission("viewer", "data_qa") returns False
   f. check_app_permission("analyst", "data_qa") returns True
   g. update_password() changes the hash
   h. toggle_user_active() flips the flag
   i. delete_user() removes the test user
3. Print PASS/FAIL for each test
4. Clean up test data on exit

Run with: python scripts/smoke_test_auth.py

--- PART C: Update README section ---

Add a new section to README.md titled "## Admin Panel & User Management" that explains:
- Default admin credentials (username: admin, password: Admin@123 — note to change in production)
- How to access the admin panel (/Admin route)
- The three roles and what each can access (table format)
- How to run setup_admin.py on a fresh install
- How to add the Admin app to the systemd startup

After running both scripts, paste the full output here so I can verify everything passed.
```

---

## Part 4 — Recommended Run Order & Time Estimates

| Step | Subagent | Est. Time | Dependency |
|---|---|---|---|
| 1 | User Database Layer | 10–15 min | None |
| 2 | Auth Layer Rewrite | 10–15 min | Subagent 1 done |
| 3 | Admin Panel App | 20–30 min | Subagent 2 done |
| 4 | RBAC Gates on 3 Apps | 5–10 min | Subagent 2 done |
| 5 | Logout Polish + Nginx | 10–15 min | Subagents 2–4 done |
| 6 | Setup Script + Smoke Test | 10–15 min | All above done |

**Total estimated build time: 60–90 minutes** (running Claude Code sequentially on each subagent prompt)

Subagents 3 and 4 can technically be run in parallel (both depend only on Subagent 2).

---

## Part 5 — Demo Script for Executives

After all subagents complete, the demo flow is:

1. **Open `/Admin`** — log in as `admin / Admin@123`
2. **Show Users tab** — live user list from database
3. **Add User tab** — create a new "analyst" user live on screen
4. **App Permissions tab** — show the RBAC matrix, toggle a permission off/on
5. **Reset Password tab** — reset the new user's password
6. **Open `/Document_AI`** in a new tab — log in as the new analyst user → show access denied (viewer-only app)
7. **Open `/Text_to_SQL`** — log in as analyst → access granted, run a query
8. **Logout** — click logout, verify redirect to login screen immediately
9. **Back to Admin** — show last_login timestamp updated for the analyst user

This sequence demonstrates: user lifecycle, RBAC enforcement, live admin control — all without touching `.env` or restarting the server.
