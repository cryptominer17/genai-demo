# Template App — Developer Guide

Use this directory as your starting point when building a new Streamlit app for the FI GenAI PoC Platform. Copy `apps/template_app/` to `apps/<your_app_name>/`, then follow the `# DEVELOPER:` annotations in `streamlit_app.py` to adapt the code for your use case.

---

## Local Run

Install shared dependencies from the repo root (if you have not done so already):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r shared/requirements.txt
```

Run the template app on a local port:

```bash
streamlit run apps/template_app/streamlit_app.py --server.port <PORT>
```

Replace `<PORT>` with the next available port from the Port Registry in
[docs/APP_DEVELOPER_VS_INFRA.md](../../docs/APP_DEVELOPER_VS_INFRA.md).
Current assignments: 8501 (Document_AI), 8502 (Text_to_SQL), 8503 (BI_Dashboard),
8504 (Admin). The next available port is **8505**.

Open `http://localhost:<PORT>` in your browser. Log in with your platform credentials
(default admin: `admin` / `Admin@123` on a fresh local database).

---

## What to Customize

The file `streamlit_app.py` contains `# DEVELOPER:` annotations at every point you
need to change. Work through them top to bottom:

1. **Module docstring** — update the app name, port, route, and one-line description.
2. **`st.set_page_config`** — set `page_title` and `page_icon` to match your app.
3. **`get_logger("template_app")`** — replace `"template_app"` with your app's directory
   name so log lines are identifiable (e.g. `"risk_scorecard"`).
4. **`require_login(..., app_name=...)`** — update `app_name` to your directory name.
5. **`require_permission(...)`** — uncomment and pass your app's permission key if you
   need role-based access control (see `shared/auth.py` for key names).
6. **Header title and subtitle** — replace emoji and text to describe your use case.
7. **Session state keys** — rename `"my_result"` and add any additional keys your app
   needs to persist between Streamlit reruns.
8. **Sidebar controls** — replace the example `text_area` with your actual inputs:
   file uploaders, dropdowns, date pickers, sliders, etc.
9. **System prompt and user prompt** — write your LLM prompts here; this is where all
   the AI logic lives.
10. **`max_tokens`** — adjust the token budget for your use case (1 500 is a safe
    default; large document summaries may need 4 000+).
11. **Result display** — replace the `st.markdown` with charts, tables, download
    buttons, or any other Streamlit output components your app needs.

---

## Dependencies

All platform apps share a single `shared/requirements.txt`. If your app needs a package
that is not already listed there:

1. Add the package (with a pinned version) to `shared/requirements.txt`.
2. Test locally: `pip install -r shared/requirements.txt`.
3. List the new package(s) in your deployment request issue so the infra team can verify
   the addition before the next deploy.

Do not create a separate `requirements.txt` inside `apps/<your_app>/`. One shared file
keeps the server environment consistent across all apps.

---

## Deployment

Before requesting deployment, complete the Handoff Checklist in
[docs/APP_DEVELOPER_VS_INFRA.md](../../docs/APP_DEVELOPER_VS_INFRA.md).

Short summary of what you need to provide to the infra team:

- [ ] `apps/<your_app>/streamlit_app.py` present and running locally without errors
- [ ] Desired URL route (e.g. `/Risk_Scorecard`) — no spaces, must be URL-safe
- [ ] Suggested port (infra assigns the final value)
- [ ] Any new environment variable **key names** (never commit values to Git)
- [ ] Any new pip packages added to `shared/requirements.txt`
- [ ] This README completed with all sections filled in
- [ ] Confirmation: "Ran locally on port XXXX with no errors on YYYY-MM-DD"
- [ ] Role access list: which roles (admin / analyst / viewer) should reach this app

Open a GitHub issue titled **"Deploy request: `<AppName>`"** and attach the completed
checklist. The infra team will assign the port, create the systemd service file, and add
the Nginx location block.

See [docs/APP_DEVELOPER_VS_INFRA.md](../../docs/APP_DEVELOPER_VS_INFRA.md) for the
full responsibility matrix and step-by-step deployment process.
