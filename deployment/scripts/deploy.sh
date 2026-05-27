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

# ── Step 6: Reload systemd ───────────────────────────────────────────────────
log "Reloading systemd daemon..."
sudo systemctl daemon-reload
log "systemd daemon reloaded."

# ── Step 7: Copy static files to web root ────────────────────────────────────
STATIC_DST="/var/www/fi-genai-poc"
log "Copying static HTML files to $STATIC_DST..."
sudo mkdir -p "$STATIC_DST/landing" "$STATIC_DST/admin"
sudo cp "$REPO_DIR/landing/index.html" "$STATIC_DST/landing/index.html"
sudo cp "$REPO_DIR/admin/index.html"   "$STATIC_DST/admin/index.html"
log "Static files updated."

# ── Step 8: Restart services ─────────────────────────────────────────────────
SERVICES=(
  streamlit-doc-intelligence
  streamlit-data-qa
  streamlit-report-generator
  streamlit-admin
  fi-genai-api
)

for service in "${SERVICES[@]}"; do
  log "Restarting $service..."
  sudo systemctl restart "$service"
  log "$service restarted. Waiting 5s before next..."
  sleep 5
done

# ── Step 9: Health checks ────────────────────────────────────────────────────
log "Running health checks..."

declare -A HEALTH_PATHS=(
  [8501]="/Document_AI/"
  [8502]="/Text_to_SQL/"
  [8503]="/BI_Dashboard/"
  [8504]="/Admin/"
)

for port in 8501 8502 8503 8504; do
  path="${HEALTH_PATHS[$port]}"
  log "Checking http://localhost:$port$path ..."
  if curl --silent --fail --max-time 30 "http://localhost:$port$path" > /dev/null; then
    log "Port $port: OK"
  else
    notify_failure "Health check failed for port $port ($path)"
    exit 1
  fi
done

log "Checking API health (port 8505)..."
if curl --silent --fail --max-time 10 "http://localhost:8505/api/health" > /dev/null; then
  log "Port 8505 (API): OK"
else
  notify_failure "Health check failed for API (port 8505)"
  exit 1
fi

# ── Step 10: Success notification ────────────────────────────────────────────
log "All health checks passed."
python3 deployment/email/notify.py "SUCCESS" "All 5 services running — deploy complete (commit: $(git rev-parse --short HEAD))"
log "=== Deployment complete ==="
