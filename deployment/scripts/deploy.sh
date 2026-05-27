#!/usr/bin/env bash
# deploy.sh — Runs on the droplet to pull latest code and restart all services
# chmod +x /opt/fi-genai-poc-platform/deployment/scripts/deploy.sh

set -e

# ── Variables ────────────────────────────────────────────────────────────────
REPO_DIR=/opt/fi-genai-poc-platform
VENV_DIR=$REPO_DIR/venv
LOG_FILE=/var/log/streamlit/deploy.log

# ── Helpers ──────────────────────────────────────────────────────────────────
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

notify_failure() {
  local msg="$1"
  log "ERROR: $msg"
  cd "$REPO_DIR"
  source "$VENV_DIR/bin/activate" 2>/dev/null || true
  python3 deployment/email/notify.py "FAILURE" "$msg" || true
}

# Trap any error and send failure notification
trap 'notify_failure "Deployment script failed at line $LINENO"' ERR

# ── Step 1: Navigate to repo ─────────────────────────────────────────────────
log "=== Starting deployment ==="
cd "$REPO_DIR"
log "Working directory: $(pwd)"

# ── Step 2: Pull latest code ─────────────────────────────────────────────────
log "Pulling latest code from origin/main..."
git pull origin main
log "Git pull complete. Commit: $(git rev-parse --short HEAD)"

# ── Step 3: Create virtualenv if missing ─────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  log "Virtual environment not found — creating at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  log "Virtual environment created."
else
  log "Virtual environment exists at $VENV_DIR."
fi

# ── Step 4: Install / update dependencies ────────────────────────────────────
log "Installing dependencies from shared/requirements.txt..."
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r shared/requirements.txt
log "Dependencies installed."

# ── Step 5: Verify .env exists ───────────────────────────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
  notify_failure ".env file is missing from $REPO_DIR — cannot start services safely."
  exit 1
fi
log ".env file found."

# ── Step 6a: Apply sysctl tuning (inotify watches for Streamlit/watchdog) ────
log "Applying sysctl tuning..."
sudo cp "$REPO_DIR/deployment/sysctl/99-fi-genai.conf" /etc/sysctl.d/99-fi-genai.conf
sudo sysctl --system --quiet 2>/dev/null || sudo sysctl -p /etc/sysctl.d/99-fi-genai.conf
log "sysctl tuning applied (fs.inotify.max_user_watches=524288)."

# ── Step 6b: Install / refresh systemd service files ─────────────────────────
log "Installing systemd service files from repo..."
sudo cp "$REPO_DIR/deployment/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fi-genai-api 2>/dev/null || true
log "Systemd services installed."

# ── Step 7: Copy static files to web root ────────────────────────────────────
STATIC_DST="/var/www/fi-genai-poc"
log "Copying static HTML files to $STATIC_DST..."
sudo mkdir -p "$STATIC_DST/landing" "$STATIC_DST/admin"
sudo cp "$REPO_DIR/landing/index.html" "$STATIC_DST/landing/index.html"
sudo cp "$REPO_DIR/admin/index.html"   "$STATIC_DST/admin/index.html"
log "Static files updated."

# ── Step 8: Restart core Streamlit services ───────────────────────────────────
CORE_SERVICES=(
  streamlit-doc-intelligence
  streamlit-data-qa
  streamlit-report-generator
)

for service in "${CORE_SERVICES[@]}"; do
  log "Restarting $service..."
  sudo systemctl restart "$service"
  log "$service restarted. Waiting 5s before next..."
  sleep 5
done

# ── Step 9: Start / restart the admin REST API ───────────────────────────────
log "Starting/restarting fi-genai-api..."
sudo systemctl restart fi-genai-api 2>/dev/null \
  || sudo systemctl start fi-genai-api 2>/dev/null \
  || log "WARNING: fi-genai-api could not be started — check: journalctl -u fi-genai-api -n 30"

# ── Step 10: Health checks — core apps ───────────────────────────────────────
log "Running health checks..."

declare -A HEALTH_PATHS=(
  [8501]="/Document_AI/"
  [8502]="/Text_to_SQL/"
  [8503]="/BI_Dashboard/"
)

for port in 8501 8502 8503; do
  path="${HEALTH_PATHS[$port]}"
  log "Checking http://localhost:$port$path ..."
  if curl --silent --fail --max-time 30 "http://localhost:$port$path" > /dev/null; then
    log "Port $port: OK"
  else
    notify_failure "Health check failed for port $port ($path)"
    exit 1
  fi
done

# ── Step 11: Health check — admin REST API (warn-only, with retry) ───────────
log "Checking Admin REST API (port 8505)..."
API_READY=false
for attempt in 1 2 3 4 5; do
  if curl --silent --fail --max-time 10 "http://localhost:8505/api/health" > /dev/null 2>&1; then
    log "Port 8505 (API): OK (attempt $attempt)"
    API_READY=true
    break
  fi
  log "Port 8505 not ready yet (attempt $attempt/5) — waiting 5s..."
  sleep 5
done
if ! $API_READY; then
  log "WARNING: Admin REST API (port 8505) not ready after 5 attempts — check: journalctl -u fi-genai-api -n 30"
fi

# ── Step 12: Done ─────────────────────────────────────────────────────────────
# Success notification is sent by the GitHub Actions workflow step.
log "All core health checks passed."
log "=== Deployment complete ==="
