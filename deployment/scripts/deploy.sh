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

# ── Step 6: Install / refresh systemd service files ──────────────────────────
log "Installing systemd service files from repo..."
sudo cp "$REPO_DIR/deployment/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload
# Enable new services (idempotent — safe to run every deploy)
sudo systemctl enable streamlit-admin fi-genai-api 2>/dev/null || true
log "Systemd services installed and enabled."

# ── Step 7: Copy static files to web root ────────────────────────────────────
STATIC_DST="/var/www/fi-genai-poc"
log "Copying static HTML files to $STATIC_DST..."
sudo mkdir -p "$STATIC_DST/landing" "$STATIC_DST/admin"
sudo cp "$REPO_DIR/landing/index.html" "$STATIC_DST/landing/index.html"
sudo cp "$REPO_DIR/admin/index.html"   "$STATIC_DST/admin/index.html"
log "Static files updated."

# ── Step 8: Restart services ─────────────────────────────────────────────────
# Core Streamlit apps — restart and wait for each
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

# Admin + API — restart (or start if not previously running)
for service in streamlit-admin fi-genai-api; do
  log "Starting/restarting $service..."
  sudo systemctl restart "$service" || sudo systemctl start "$service" || \
    log "WARNING: Could not restart $service — it may need manual attention."
  sleep 3
done

# ── Step 9: Health checks ────────────────────────────────────────────────────
log "Running health checks..."

# Helper: retry a curl check up to N times with a delay between attempts.
check_port_retry() {
  local port="$1"
  local path="$2"
  local label="$3"
  local tries="${4:-3}"
  local wait="${5:-10}"
  for i in $(seq 1 "$tries"); do
    if curl --silent --fail --max-time 30 "http://localhost:${port}${path}" > /dev/null 2>&1; then
      log "Port $port ($label): OK"
      return 0
    fi
    log "Port $port ($label): attempt $i/$tries failed — waiting ${wait}s..."
    sleep "$wait"
  done
  return 1
}

# Core apps — must pass or deploy fails
declare -A HEALTH_PATHS=(
  [8501]="/Document_AI/"
  [8502]="/Text_to_SQL/"
  [8503]="/BI_Dashboard/"
)
for port in 8501 8502 8503; do
  path="${HEALTH_PATHS[$port]}"
  if ! check_port_retry "$port" "$path" "core" 3 10; then
    notify_failure "Health check failed for port $port ($path)"
    exit 1
  fi
done

# Admin Streamlit (8504) — Streamlit takes longer; warn but don't fail deploy
log "Checking Admin Streamlit (port 8504) — allows longer startup..."
if check_port_retry 8504 "/Admin/" "admin" 6 10; then
  log "Port 8504 (Admin): OK"
else
  log "WARNING: Admin Streamlit (port 8504) not yet ready — deploy continues."
  log "         Check: journalctl -u streamlit-admin -n 50 --no-pager"
fi

# REST API (8505) — fast startup; warn but don't fail deploy on first install
log "Checking Admin REST API (port 8505)..."
if check_port_retry 8505 "/api/health" "api" 3 5; then
  log "Port 8505 (API): OK"
else
  log "WARNING: Admin REST API (port 8505) not ready — deploy continues."
  log "         Check: journalctl -u fi-genai-api -n 50 --no-pager"
fi

# ── Step 10: Success notification ────────────────────────────────────────────
log "Core health checks passed."
python3 deployment/email/notify.py "SUCCESS" \
  "Core services running — deploy complete (commit: $(git rev-parse --short HEAD))" || true
log "=== Deployment complete ==="
