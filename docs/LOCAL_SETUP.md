# Local Development Setup

How to run the FI GenAI PoC Platform apps on your local machine for development and testing.

---

## Prerequisites

- **Python 3.10 or higher**
  - Check: `python3 --version`
  - Install: [python.org/downloads](https://python.org/downloads) or `brew install python@3.11` (macOS)
- **git**
  - Check: `git --version`
- **Anthropic API key**
  - Get one at [console.anthropic.com](https://console.anthropic.com)
  - Free tier is sufficient for local testing

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/cryptominer17/genai-demo.git
cd genai-demo
```

---

## Step 2 — Create a Virtual Environment

```bash
# Create the venv
python3 -m venv venv

# Activate it
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows (Command Prompt)
# venv\Scripts\Activate.ps1       # Windows (PowerShell)
```

You should see `(venv)` in your terminal prompt.

---

## Step 3 — Install Dependencies

```bash
pip install --upgrade pip
pip install -r shared/requirements.txt
```

This installs Streamlit, the Anthropic SDK, and all shared dependencies. Takes 1–3 minutes on first install.

---

## Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...    # your key from console.anthropic.com
APP_SECRET_KEY=any-random-string-32-chars-or-longer
COOKIE_KEY=another-random-string-32-chars-or-longer
```

The `.env` file is gitignored — it will never be committed.

---

## Step 5 — Run an App

Each app can be run independently:

**Document Intelligence (port 8501):**
```bash
streamlit run apps/document_intelligence/streamlit_app.py --server.port 8501
```

**Data Q&A / Text-to-SQL (port 8502):**
```bash
streamlit run apps/data_qa/streamlit_app.py --server.port 8502
```

**Report Generator (port 8503):**
```bash
streamlit run apps/report_generator/streamlit_app.py --server.port 8503
```

---

## Step 6 — Open the App

Streamlit will automatically open a browser tab. If not, navigate to:
- http://localhost:8501 (Document Intelligence)
- http://localhost:8502 (Data Q&A)
- http://localhost:8503 (Report Generator)

Note: when running locally, you do **not** use the `/Document_AI` path prefix — that's only used in production behind Nginx. Locally, apps run at the root path.

---

## Step 7 — Running All Three Simultaneously

Open three separate terminal tabs/windows, activate the venv in each, and run one app per terminal.

**Terminal 1:**
```bash
cd genai-demo && source venv/bin/activate
streamlit run apps/document_intelligence/streamlit_app.py --server.port 8501
```

**Terminal 2:**
```bash
cd genai-demo && source venv/bin/activate
streamlit run apps/data_qa/streamlit_app.py --server.port 8502
```

**Terminal 3:**
```bash
cd genai-demo && source venv/bin/activate
streamlit run apps/report_generator/streamlit_app.py --server.port 8503
```

All three will run independently — each has its own session state and log output in its terminal.

---

## Deactivating the Virtual Environment

When you're done:
```bash
deactivate
```

---

## Common Local Issues

**"command not found: streamlit"**
You likely forgot to activate the venv, or ran `pip install` outside the venv.
```bash
source venv/bin/activate
pip install -r shared/requirements.txt
```

**"ModuleNotFoundError: No module named 'anthropic'"** (or similar)
```bash
pip install -r shared/requirements.txt
```

**"Address already in use (port 850x)"**
Another process is using that port. Find and kill it:
```bash
lsof -i :8501          # find the PID
kill <PID>
# Or use a different port: --server.port 8510
```

**App loads but LLM features fail with "authentication error"**
Check your `.env` — the `ANTHROPIC_API_KEY` may be missing, expired, or have a typo.
```bash
cat .env | grep ANTHROPIC
```

**Changes not reflecting after editing code**
Streamlit has hot-reload enabled by default — changes to `.py` files should reload automatically. If not, press `R` in the Streamlit browser UI to force a rerun. For config/shared module changes, stop and restart the app.

**Login page appears but credentials rejected**
Check `APP_SECRET_KEY` and `COOKIE_KEY` are set in `.env`. If the keys changed between runs, clear your browser cookies for `localhost`.

---

## Development Tips

- Edit `shared/llm_client.py` to adjust system prompts, model selection, or temperature without touching app code.
- Use `st.write()` or `st.json()` liberally for debugging — Streamlit renders Python objects directly.
- Streamlit's `--server.runOnSave true` (default) triggers a rerun on file save.
- Check `~/.streamlit/config.toml` if you want to customize default Streamlit behavior globally.
