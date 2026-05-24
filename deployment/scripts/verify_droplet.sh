#!/usr/bin/env bash
# verify_droplet.sh — Pre-deployment verification for FI GenAI PoC Platform
# Run this on the Digital Ocean droplet before deploying apps.
# Usage: bash verify_droplet.sh

set -uo pipefail

# ------------------------------------------------------------------ #
# Color helpers
# ------------------------------------------------------------------ #
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}[PASS]${NC} $1"; (( PASS++ )); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; (( FAIL++ )); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; (( WARN++ )); }

APP_DIR="/opt/fi-genai-poc-platform"
LOG_DIR="/var/log/streamlit"
DEPLOY_USER="streamlit"

echo ""
echo -e "${BOLD}======================================================${NC}"
echo -e "${BOLD} FI GenAI PoC Platform — Droplet Pre-flight Check${NC}"
echo -e "${BOLD} $(date '+%Y-%m-%d %H:%M:%S %Z')${NC}"
echo -e "${BOLD}======================================================${NC}"
echo ""

# ------------------------------------------------------------------ #
# 1. Python 3 version (require >= 3.10)
# ------------------------------------------------------------------ #
echo "--- Python & pip ---"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if (( PY_MAJOR > 3 )) || (( PY_MAJOR == 3 && PY_MINOR >= 10 )); then
        pass "Python $PY_VERSION found (>= 3.10 required)"
    else
        fail "Python $PY_VERSION found — need >= 3.10. Install: sudo apt install python3.10"
    fi
else
    fail "python3 not found. Install: sudo apt install python3"
fi

# ------------------------------------------------------------------ #
# 2. pip3 available
# ------------------------------------------------------------------ #
if command -v pip3 &>/dev/null; then
    PIP_VER=$(pip3 --version | awk '{print $2}')
    pass "pip3 $PIP_VER available"
else
    fail "pip3 not found. Install: sudo apt install python3-pip"
fi

# ------------------------------------------------------------------ #
# 3. git available
# ------------------------------------------------------------------ #
echo ""
echo "--- System Tools ---"
if command -v git &>/dev/null; then
    GIT_VER=$(git --version | awk '{print $3}')
    pass "git $GIT_VER available"
else
    fail "git not found. Install: sudo apt install git"
fi

# ------------------------------------------------------------------ #
# 4. nginx installed and config valid
# ------------------------------------------------------------------ #
if command -v nginx &>/dev/null; then
    NGINX_VER=$(nginx -v 2>&1 | grep -oP '[\d.]+' | head -1)
    pass "nginx $NGINX_VER installed"
    if nginx -t 2>/dev/null; then
        pass "nginx config test passed (nginx -t)"
    else
        fail "nginx config test failed — run 'nginx -t' for details"
    fi
else
    fail "nginx not found. Install: sudo apt install nginx"
fi

# ------------------------------------------------------------------ #
# 5. App directory exists and is owned by streamlit user
# ------------------------------------------------------------------ #
echo ""
echo "--- App Directory ---"
if [[ -d "$APP_DIR" ]]; then
    DIR_OWNER=$(stat -c '%U' "$APP_DIR" 2>/dev/null || echo "unknown")
    if [[ "$DIR_OWNER" == "$DEPLOY_USER" ]]; then
        pass "$APP_DIR exists and is owned by '$DEPLOY_USER'"
    else
        fail "$APP_DIR owned by '$DIR_OWNER', expected '$DEPLOY_USER'. Fix: sudo chown -R streamlit:streamlit $APP_DIR"
    fi
else
    fail "$APP_DIR does not exist. Create: sudo mkdir -p $APP_DIR && sudo chown streamlit:streamlit $APP_DIR"
fi

# ------------------------------------------------------------------ #
# 6. Log directory exists
# ------------------------------------------------------------------ #
echo ""
echo "--- Log Directory ---"
if [[ -d "$LOG_DIR" ]]; then
    LOG_OWNER=$(stat -c '%U' "$LOG_DIR" 2>/dev/null || echo "unknown")
    pass "$LOG_DIR exists (owner: $LOG_OWNER)"
    if [[ "$LOG_OWNER" != "$DEPLOY_USER" ]]; then
        warn "$LOG_DIR owner is '$LOG_OWNER', not '$DEPLOY_USER'. Fix: sudo chown -R streamlit:streamlit $LOG_DIR"
    fi
else
    fail "$LOG_DIR does not exist. Create: sudo mkdir -p $LOG_DIR && sudo chown streamlit:streamlit $LOG_DIR"
fi

# ------------------------------------------------------------------ #
# 7. .env file exists (warn only — may not exist before first deploy)
# ------------------------------------------------------------------ #
echo ""
echo "--- Environment File ---"
if [[ -f "${APP_DIR}/.env" ]]; then
    pass ".env file found at ${APP_DIR}/.env"
else
    warn ".env not found at ${APP_DIR}/.env — create it before starting services (see .env.example)"
fi

# ------------------------------------------------------------------ #
# 8. Virtual environment exists
# ------------------------------------------------------------------ #
echo ""
echo "--- Python Virtual Environment ---"
if [[ -f "${APP_DIR}/venv/bin/python" ]]; then
    VENV_PY=$(${APP_DIR}/venv/bin/python --version 2>&1)
    pass "venv found — $VENV_PY"
else
    fail "venv not found at ${APP_DIR}/venv. Create: cd $APP_DIR && python3 -m venv venv && venv/bin/pip install -r shared/requirements.txt"
fi

# ------------------------------------------------------------------ #
# 9. systemd service files installed
# ------------------------------------------------------------------ #
echo ""
echo "--- systemd Service Files ---"
SERVICES=(
    "streamlit-doc-intelligence"
    "streamlit-data-qa"
    "streamlit-report-generator"
)
for svc in "${SERVICES[@]}"; do
    if [[ -f "/etc/systemd/system/${svc}.service" ]]; then
        pass "/etc/systemd/system/${svc}.service installed"
    else
        fail "${svc}.service not in /etc/systemd/system/. Copy from deployment/systemd/ and run: sudo systemctl daemon-reload"
    fi
done

# ------------------------------------------------------------------ #
# 10. UFW status — ports 22 and 80 open
# ------------------------------------------------------------------ #
echo ""
echo "--- Firewall (UFW) ---"
if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1 | awk '{print $2}')
    if [[ "$UFW_STATUS" == "active" ]]; then
        pass "UFW is active"
        # Check port 22
        if ufw status | grep -qE "^22.*ALLOW"; then
            pass "UFW: port 22 (SSH) is open"
        else
            fail "UFW: port 22 (SSH) not open — risk of lockout! Run: sudo ufw allow 22"
        fi
        # Check port 80
        if ufw status | grep -qE "^80.*ALLOW|^Nginx.*ALLOW"; then
            pass "UFW: port 80 (HTTP) is open"
        else
            fail "UFW: port 80 (HTTP) not open. Run: sudo ufw allow 80"
        fi
    else
        warn "UFW is inactive — consider enabling: sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw enable"
    fi
else
    warn "UFW not installed. Install: sudo apt install ufw"
fi

# ------------------------------------------------------------------ #
# Summary
# ------------------------------------------------------------------ #
echo ""
echo -e "${BOLD}======================================================${NC}"
echo -e " Results: ${GREEN}${PASS} passed${NC} | ${RED}${FAIL} failed${NC} | ${YELLOW}${WARN} warnings${NC}"
echo -e "${BOLD}======================================================${NC}"

if (( FAIL > 0 )); then
    echo -e "${RED} Fix all FAIL items before deploying.${NC}"
    echo ""
    exit 1
elif (( WARN > 0 )); then
    echo -e "${YELLOW} Warnings present — review before deploying.${NC}"
    echo ""
    exit 0
else
    echo -e "${GREEN} All checks passed. Droplet is ready for deployment.${NC}"
    echo ""
    exit 0
fi
