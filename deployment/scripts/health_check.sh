#!/usr/bin/env bash
# health_check.sh — Comprehensive health check for FI GenAI PoC Platform
# Usage:
#   bash health_check.sh          # Human-readable colored output
#   bash health_check.sh --json   # JSON output for monitoring integrations

set -euo pipefail

# ------------------------------------------------------------------ #
# Color helpers
# ------------------------------------------------------------------ #
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

JSON_MODE=false
[[ "${1:-}" == "--json" ]] && JSON_MODE=true

# Accumulate results for JSON output
declare -A RESULTS
OVERALL=0

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; RESULTS["$2"]="ok"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; RESULTS["$2"]="fail"; OVERALL=1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; RESULTS["$2"]="warn"; }

# ------------------------------------------------------------------ #
# 1. Systemd service status
# ------------------------------------------------------------------ #
check_service() {
    local svc="$1"
    local label="$2"
    if systemctl is-active --quiet "$svc"; then
        ok "$svc is active" "$label"
    else
        fail "$svc is NOT active (run: journalctl -u $svc -n 20)" "$label"
    fi
}

echo ""
echo "========================================"
echo " FI GenAI PoC Platform — Health Check"
echo " $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "========================================"
echo ""

echo "--- Systemd Services ---"
check_service "streamlit-doc-intelligence"  "svc_doc_intelligence"
check_service "streamlit-data-qa"           "svc_data_qa"
check_service "streamlit-report-generator"  "svc_report_generator"

# ------------------------------------------------------------------ #
# 2. HTTP reachability on each port
# ------------------------------------------------------------------ #
echo ""
echo "--- App Ports (localhost) ---"

check_port() {
    local port="$1"
    local label="$2"
    local name="$3"
    local http_code
    http_code=$(curl --silent --fail --max-time 10 \
        --write-out "%{http_code}" --output /dev/null \
        "http://localhost:${port}" 2>/dev/null || echo "000")

    if [[ "$http_code" =~ ^(200|301|302|303|307|308)$ ]]; then
        ok "Port $port ($name) — HTTP $http_code" "$label"
    else
        fail "Port $port ($name) — HTTP $http_code (not reachable)" "$label"
    fi
}

check_port 8501 "port_8501" "Document Intelligence"
check_port 8502 "port_8502" "Data Q&A"
check_port 8503 "port_8503" "Report Generator"

# ------------------------------------------------------------------ #
# 3. Nginx
# ------------------------------------------------------------------ #
echo ""
echo "--- Nginx ---"

if systemctl is-active --quiet nginx; then
    ok "nginx service is active" "nginx_service"
else
    fail "nginx is NOT active (run: systemctl status nginx)" "nginx_service"
fi

if nginx -t 2>/dev/null; then
    ok "nginx config test passed" "nginx_config"
else
    fail "nginx config test FAILED (run: nginx -t)" "nginx_config"
fi

# ------------------------------------------------------------------ #
# 4. Recent error log entries
# ------------------------------------------------------------------ #
echo ""
echo "--- Recent Error Logs (last 10 lines each) ---"

LOG_DIR="/var/log/streamlit"
check_error_log() {
    local logfile="$1"
    local label="$2"
    local appname="$3"

    if [[ ! -f "$logfile" ]]; then
        warn "$appname error log not found: $logfile" "$label"
        return
    fi

    local lines
    lines=$(tail -n 10 "$logfile" 2>/dev/null || true)

    if echo "$lines" | grep -qiE "(error|exception|traceback|critical)" 2>/dev/null; then
        fail "$appname has recent errors in $logfile" "$label"
        echo "      Last 10 lines:"
        echo "$lines" | sed 's/^/      /'
    else
        ok "$appname error log looks clean" "$label"
    fi
}

check_error_log "${LOG_DIR}/doc-intelligence-error.log"  "log_doc"  "Document Intelligence"
check_error_log "${LOG_DIR}/data-qa-error.log"           "log_qa"   "Data Q&A"
check_error_log "${LOG_DIR}/report-generator-error.log"  "log_rpt"  "Report Generator"

# ------------------------------------------------------------------ #
# 5. Disk space (warn if >85%)
# ------------------------------------------------------------------ #
echo ""
echo "--- Disk Space ---"
DISK_USED=$(df /opt 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
if [[ -n "$DISK_USED" ]]; then
    if (( DISK_USED >= 90 )); then
        fail "Disk usage at ${DISK_USED}% — critical" "disk"
    elif (( DISK_USED >= 85 )); then
        warn "Disk usage at ${DISK_USED}% — approaching limit" "disk"
    else
        ok "Disk usage at ${DISK_USED}%" "disk"
    fi
fi

# ------------------------------------------------------------------ #
# Summary
# ------------------------------------------------------------------ #
echo ""
echo "========================================"
if [[ $OVERALL -eq 0 ]]; then
    echo -e "${GREEN} All checks passed.${NC}"
else
    echo -e "${RED} One or more checks FAILED. Review above.${NC}"
fi
echo "========================================"
echo ""

# ------------------------------------------------------------------ #
# JSON output
# ------------------------------------------------------------------ #
if $JSON_MODE; then
    echo ""
    echo "--- JSON Output ---"
    python3 - <<PYEOF
import json, sys
results = {}
PYEOF
    # Build JSON manually (no python dependency assumption)
    printf '{\n  "timestamp": "%s",\n  "overall": "%s",\n  "checks": {\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        "$( [[ $OVERALL -eq 0 ]] && echo ok || echo fail )"

    first=true
    for key in "${!RESULTS[@]}"; do
        $first || printf ',\n'
        printf '    "%s": "%s"' "$key" "${RESULTS[$key]}"
        first=false
    done
    printf '\n  }\n}\n'
fi

exit $OVERALL
