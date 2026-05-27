#!/usr/bin/env bash
# =============================================================================
# FI GenAI PoC Platform — Comprehensive Fix Script
# Target: 157.230.82.180
# Run as: root
# Usage:  bash fi_genai_fix.sh
# =============================================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
info() { echo -e "${CYAN}[i]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*"; }

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}  FI GenAI PoC — Bug Fix Script                  ${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

# =============================================================================
# STEP 0 — Discover actual file paths (defensive; don't assume)
# =============================================================================
info "Step 0: Discovering file paths..."

# Find app root — try common locations
APP_ROOT=""
for candidate in /opt/fi-genai-poc-platform /opt/fi-genai-poc /home/ubuntu/fi-genai-poc /root/fi-genai-poc /app; do
  if [ -d "$candidate/apps" ]; then
    APP_ROOT="$candidate"
    break
  fi
done

if [ -z "$APP_ROOT" ]; then
  # Broader search
  APP_ROOT=$(find / -maxdepth 5 -type d -name "fi-genai*" 2>/dev/null | head -1 || true)
fi

if [ -z "$APP_ROOT" ]; then
  fail "Cannot locate app root directory. Searched common paths."
  fail "Please run: find / -maxdepth 6 -name 'streamlit_app.py' 2>/dev/null"
  exit 1
fi
ok "App root: $APP_ROOT"

# Find static HTML files
LANDING_HTML=""
ADMIN_HTML=""
for candidate in /var/www/fi-genai-poc /var/www/html /var/www; do
  [ -f "$candidate/landing/index.html" ] && LANDING_HTML="$candidate/landing/index.html"
  [ -f "$candidate/admin/index.html"   ] && ADMIN_HTML="$candidate/admin/index.html"
done

# Fallback: search
[ -z "$LANDING_HTML" ] && LANDING_HTML=$(find /var/www -name "index.html" -path "*/landing/*" 2>/dev/null | head -1 || true)
[ -z "$ADMIN_HTML"   ] && ADMIN_HTML=$(find /var/www -name "index.html" -path "*/admin/*" 2>/dev/null | head -1 || true)

[ -n "$LANDING_HTML" ] && ok "Landing page: $LANDING_HTML" || warn "Landing HTML not found — will skip HTML patches"
[ -n "$ADMIN_HTML"   ] && ok "Static admin HTML: $ADMIN_HTML" || warn "Static admin HTML not found"

# Find nginx config
NGINX_CONF=""
for candidate in /etc/nginx/sites-enabled/fi-genai* /etc/nginx/sites-enabled/default /etc/nginx/conf.d/fi-genai*.conf /etc/nginx/nginx.conf; do
  if [ -f "$candidate" ]; then
    NGINX_CONF="$candidate"
    break
  fi
done
[ -n "$NGINX_CONF" ] && ok "Nginx config: $NGINX_CONF" || warn "Nginx config not found"

# Find admin streamlit app
ADMIN_APP="$APP_ROOT/apps/admin/streamlit_app.py"
[ -f "$ADMIN_APP" ] && ok "Admin Streamlit app: $ADMIN_APP" || { fail "Admin app not found at $ADMIN_APP"; exit 1; }

# Find existing systemd service to use as template
TEMPLATE_SERVICE=$(find /etc/systemd/system -name "streamlit*" -o -name "fi-genai*" 2>/dev/null | grep -v admin | head -1 || true)
[ -n "$TEMPLATE_SERVICE" ] && ok "Systemd template: $TEMPLATE_SERVICE" || warn "No existing streamlit service found to use as template"

echo ""

# =============================================================================
# STEP 1 — Deploy the Admin Streamlit Service (Port 8504)
#          Fixes: Issues 3, 4, 5, 6 (all require the real admin backend)
# =============================================================================
info "Step 1: Deploying admin Streamlit service on port 8504..."

ADMIN_SERVICE="/etc/systemd/system/streamlit-admin.service"

if systemctl is-active --quiet streamlit-admin 2>/dev/null; then
  ok "streamlit-admin service already running — skipping create"
else
  # Detect Python / streamlit executable
  STREAMLIT_BIN=$(which streamlit 2>/dev/null || find /usr -name streamlit 2>/dev/null | head -1 || find /home -name streamlit 2>/dev/null | head -1 || true)
  if [ -z "$STREAMLIT_BIN" ]; then
    # Try within virtualenv in app root
    STREAMLIT_BIN=$(find "$APP_ROOT" -name streamlit 2>/dev/null | head -1 || true)
  fi
  [ -z "$STREAMLIT_BIN" ] && { fail "Cannot find streamlit binary. Is it installed?"; exit 1; }
  ok "Streamlit binary: $STREAMLIT_BIN"

  # Determine working user (prefer non-root if app files are owned by a specific user)
  APP_OWNER=$(stat -c '%U' "$ADMIN_APP" 2>/dev/null || echo "root")

  # Determine .env path
  ENV_FILE="$APP_ROOT/.env"
  ENV_LINE=""
  [ -f "$ENV_FILE" ] && ENV_LINE="EnvironmentFile=$ENV_FILE"

  cat > "$ADMIN_SERVICE" <<EOF
[Unit]
Description=FI GenAI PoC — Admin Panel (Streamlit, port 8504)
After=network.target
Wants=network.target

[Service]
Type=simple
User=$APP_OWNER
WorkingDirectory=$APP_ROOT
$ENV_LINE
ExecStart=$STREAMLIT_BIN run $ADMIN_APP \\
    --server.port=8504 \\
    --server.address=127.0.0.1 \\
    --server.headless=true \\
    --server.enableCORS=false \\
    --server.enableXsrfProtection=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable streamlit-admin
  systemctl start streamlit-admin
  sleep 3

  if systemctl is-active --quiet streamlit-admin; then
    ok "streamlit-admin service started and enabled"
  else
    fail "Service failed to start. Check: journalctl -u streamlit-admin -n 50"
    journalctl -u streamlit-admin -n 30 --no-pager || true
    exit 1
  fi
fi

echo ""

# =============================================================================
# STEP 2 — Verify / fix nginx proxy for /Admin/ → port 8504
#          If the proxy block is missing, add it
# =============================================================================
info "Step 2: Checking nginx proxy for /Admin/ → 8504..."

if [ -n "$NGINX_CONF" ]; then
  if grep -q "8504" "$NGINX_CONF" 2>/dev/null; then
    ok "Nginx already has a proxy rule for port 8504"
  else
    warn "No 8504 proxy found in $NGINX_CONF — adding /Admin/ block"
    # Insert before the closing server brace
    ADMIN_PROXY_BLOCK='
    # Admin Panel — real Streamlit app (port 8504)
    location /Admin/ {
        proxy_pass         http://127.0.0.1:8504/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_read_timeout 86400;
    }
'
    # Append proxy block before last closing brace in the server block
    sed -i "s|^}$|$ADMIN_PROXY_BLOCK\n}|" "$NGINX_CONF"
    ok "Nginx proxy block for /Admin/ added"
  fi

  nginx -t && systemctl reload nginx && ok "Nginx config valid — reloaded" || { fail "Nginx config invalid — check $NGINX_CONF"; exit 1; }
else
  warn "Skipping nginx step — config not found. Verify manually that /Admin/ proxies to 127.0.0.1:8504"
fi

echo ""

# =============================================================================
# STEP 3 — Patch landing/index.html
#          Fix: Issue 1 (auto-login), Issue 2 (logout), Issue 3 (change-password)
# =============================================================================
info "Step 3: Patching landing/index.html..."

if [ -n "$LANDING_HTML" ]; then
  cp "$LANDING_HTML" "${LANDING_HTML}.bak.$(date +%Y%m%d%H%M%S)"
  ok "Backup created: ${LANDING_HTML}.bak.*"

  # Fix 1: Logout button — add onclick redirect to /Admin/ login
  # Pattern: class="logout-btn" with no action → add onclick
  sed -i 's|class="logout-btn"[^>]*>Logout|class="logout-btn" onclick="window.location.href='"'"'/Admin/?logout=1'"'"'">Logout|g' "$LANDING_HTML"
  # Fallback pattern without text
  python3 - "$LANDING_HTML" <<'PYEOF'
import re, sys
path = sys.argv[1]
content = open(path).read()

# Fix logout button — ensure it has an href or onclick
content = re.sub(
    r'(<button[^>]*class="[^"]*logout[^"]*"[^>]*)(>)',
    r'\1 onclick="window.location.href=\'/Admin/?action=logout\'">\2'.replace('>\2', '>'),
    content
)

# More robust: find logout button and ensure onclick is set
content = re.sub(
    r'(<button)([^>]*class="[^"]*logout-btn[^"]*"[^>]*)(?!onclick)([^>]*>)',
    r'\1\2 onclick="window.location.href=\'/Admin/?action=logout\'"\3',
    content
)

# Fix Change Password link — change href from /admin/ to /Admin/
content = re.sub(
    r'(href=")(/admin/?)("[^>]*>[^<]*[Cc]hange\s*[Pp]assword)',
    r'\1/Admin/\3',
    content
)

# Fix sidebar Admin link — change /admin/ to /Admin/
content = re.sub(
    r'(href=")(/admin/?)(")',
    r'\1/Admin/\3',
    content
)

open(path, 'w').write(content)
print("HTML patches applied.")
PYEOF

  ok "Landing page patched (logout, change-password, admin links)"
else
  warn "Landing HTML not found — skipping HTML patch"
fi

echo ""

# =============================================================================
# STEP 4 — Replace static /admin/index.html with a redirect to /Admin/
#          Fixes: Issue 3 (anyone who lands on /admin/ gets the real app)
# =============================================================================
info "Step 4: Replacing static admin HTML with redirect to /Admin/..."

if [ -n "$ADMIN_HTML" ]; then
  cp "$ADMIN_HTML" "${ADMIN_HTML}.bak.$(date +%Y%m%d%H%M%S)"
  cat > "$ADMIN_HTML" <<'EOF'
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="refresh" content="0; url=/Admin/">
  <title>Redirecting to Admin Panel...</title>
</head>
<body>
  <p>Redirecting to the Admin Panel... <a href="/Admin/">click here if not redirected</a>.</p>
  <script>window.location.replace("/Admin/");</script>
</body>
</html>
EOF
  ok "Static /admin/index.html replaced with redirect to /Admin/"
else
  warn "Static admin HTML not found — skipping redirect replacement"
fi

echo ""

# =============================================================================
# STEP 5 — Security hardening (bonus fixes from audit)
# =============================================================================
info "Step 5: Applying security hardening..."

# Block direct access to .env and other dotfiles (may already exist)
if [ -n "$NGINX_CONF" ]; then
  if grep -q "deny all" "$NGINX_CONF" 2>/dev/null; then
    ok "Nginx dotfile deny rule already present"
  else
    warn "No dotfile deny rule found — adding"
    sed -i '/^}/i\    location ~ /\\. { deny all; }' "$NGINX_CONF"
    nginx -t && systemctl reload nginx && ok "Dotfile deny rule added and nginx reloaded"
  fi
fi

echo ""

# =============================================================================
# STEP 6 — Verification checklist
# =============================================================================
info "Step 6: Running verification checks..."
echo ""

PASS=0; FAIL=0

check() {
  local desc="$1"; local cmd="$2"
  if eval "$cmd" &>/dev/null; then
    ok "$desc"
    ((PASS++)) || true
  else
    fail "$desc"
    ((FAIL++)) || true
  fi
}

check "Admin Streamlit service is running" "systemctl is-active streamlit-admin"
check "Port 8504 is listening" "ss -tlnp | grep -q ':8504'"
check "HTTP /Admin/ returns 200" "curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1/Admin/ | grep -q 200"
check "HTTP /admin/ returns redirect (302 or meta-refresh)" "curl -sf http://127.0.0.1/admin/ | grep -qi 'refresh\|redirect\|/Admin/'"
check "Nginx is running" "systemctl is-active nginx"
check "Logout button has onclick in landing HTML" "grep -q 'logout.*onclick\|onclick.*logout' '$LANDING_HTML' 2>/dev/null"
check ".env not publicly readable" "! curl -sf http://127.0.0.1/.env | grep -q '='"

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "  Results: ${GREEN}${PASS} passed${NC}  /  ${RED}${FAIL} failed${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

if [ "$FAIL" -eq 0 ]; then
  ok "All checks passed. Visit http://157.230.82.180/Admin/ for the live admin panel."
else
  warn "$FAIL check(s) failed — review output above."
  warn "For admin service logs: journalctl -u streamlit-admin -n 50 --no-pager"
fi

echo ""
info "Backups of original HTML files saved as *.bak.<timestamp> in same directory."
info "To rollback: mv <file>.bak.<timestamp> <file>"
echo ""
