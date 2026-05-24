#!/bin/bash
# =============================================================================
# setup_droplet.sh
# Bootstrap script for fi-genai-poc-platform on Ubuntu 22.04
# Digital Ocean droplet — run as root on first login
# =============================================================================

set -e  # Exit immediately on any command failure

echo "=============================================="
echo " FI GenAI PoC Platform — Droplet Bootstrap"
echo "=============================================="
echo ""

# ------------------------------------------------------------------------------
# 1. System update and upgrade
# ------------------------------------------------------------------------------
echo "[1/7] Updating and upgrading system packages..."
apt-get update -y
apt-get upgrade -y
echo "      Done."

# ------------------------------------------------------------------------------
# 2. Install required packages
# ------------------------------------------------------------------------------
echo "[2/7] Installing required packages..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    curl \
    ufw
echo "      Done."

# ------------------------------------------------------------------------------
# 3. Create non-root user 'streamlit' with sudo privileges
# ------------------------------------------------------------------------------
echo "[3/7] Creating non-root user 'streamlit'..."

if id "streamlit" &>/dev/null; then
    echo "      User 'streamlit' already exists — skipping creation."
else
    useradd -m -s /bin/bash streamlit
    usermod -aG sudo streamlit
    # Disable password login; access via SSH key only
    passwd -l streamlit
    echo "      User 'streamlit' created with sudo privileges."
fi

# ------------------------------------------------------------------------------
# 4. Create application and log directories
# ------------------------------------------------------------------------------
echo "[4/7] Creating app and log directories..."

APP_DIR="/opt/fi-genai-poc-platform"
LOG_DIR="/var/log/streamlit"

mkdir -p "$APP_DIR"
chown streamlit:streamlit "$APP_DIR"
chmod 755 "$APP_DIR"

mkdir -p "$LOG_DIR"
chown streamlit:streamlit "$LOG_DIR"
chmod 755 "$LOG_DIR"

echo "      App directory : $APP_DIR (owner: streamlit)"
echo "      Log directory : $LOG_DIR (owner: streamlit)"

# ------------------------------------------------------------------------------
# 5. Configure UFW firewall
# ------------------------------------------------------------------------------
echo "[5/7] Configuring UFW firewall..."

ufw --force reset           # Reset to clean state
ufw default deny incoming   # Deny all inbound by default
ufw default allow outgoing  # Allow all outbound by default

ufw allow 22/tcp   comment 'SSH'
ufw allow 80/tcp   comment 'HTTP'
ufw allow 443/tcp  comment 'HTTPS'

# Enable UFW non-interactively
ufw --force enable

echo "      UFW enabled. Allowed: 22/tcp, 80/tcp, 443/tcp"
ufw status verbose

# ------------------------------------------------------------------------------
# 6. Generate SSH ed25519 key pair for streamlit user
# ------------------------------------------------------------------------------
echo "[6/7] Generating SSH ed25519 key pair for 'streamlit' user..."

SSH_DIR="/home/streamlit/.ssh"
KEY_PATH="$SSH_DIR/id_ed25519"

mkdir -p "$SSH_DIR"
chown streamlit:streamlit "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ -f "$KEY_PATH" ]; then
    echo "      SSH key already exists at $KEY_PATH — skipping generation."
else
    # Generate key as the streamlit user (no passphrase)
    sudo -u streamlit ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "streamlit@fi-genai-poc-platform"
    echo "      SSH key generated at $KEY_PATH"
fi

# Ensure correct permissions on key files
chown streamlit:streamlit "$KEY_PATH" "$KEY_PATH.pub"
chmod 600 "$KEY_PATH"
chmod 644 "$KEY_PATH.pub"

# ------------------------------------------------------------------------------
# 7. Start and enable nginx
# ------------------------------------------------------------------------------
echo "[7/7] Starting and enabling nginx..."
systemctl enable nginx
systemctl start nginx
echo "      nginx is running."

# ------------------------------------------------------------------------------
# Summary and next steps
# ------------------------------------------------------------------------------
echo ""
echo "=============================================="
echo " Bootstrap complete!"
echo "=============================================="
echo ""
echo "  App directory : /opt/fi-genai-poc-platform"
echo "  Log directory : /var/log/streamlit"
echo "  User          : streamlit (sudo-enabled, SSH key only)"
echo ""
echo "----------------------------------------------"
echo " NEXT STEP: Add the SSH public key to GitHub"
echo " Deploy Keys for your repository."
echo ""
echo " Copy the public key below:"
echo "----------------------------------------------"
cat /home/streamlit/.ssh/id_ed25519.pub
echo "----------------------------------------------"
echo ""
echo " In GitHub:"
echo "   1. Go to your repo → Settings → Deploy keys"
echo "   2. Click 'Add deploy key'"
echo "   3. Title: fi-genai-poc-platform droplet"
echo "   4. Paste the key above"
echo "   5. Check 'Allow write access' if needed for push"
echo "   6. Click 'Add key'"
echo ""
echo " Also record this droplet's static IP for GitHub"
echo " Actions secrets (DROPLET_HOST):"
hostname -I | awk '{print $1}'
echo ""
