# Pre-Deployment Checklist — FI GenAI PoC Platform

Complete every item in order before running `deploy.sh` for the first time.
Check off each item as you go. Do not skip sections — each depends on the previous.

---

## Section A: Digital Ocean Droplet

- [ ] Create droplet: Ubuntu 22.04 LTS, 2 GB RAM / 1 vCPU ($12/mo), Virginia (NYC3 or SFO3 — pick closest to VA), hostname `fi-genai-poc-platform`
- [ ] Note the static IP address — you will need it in Section B and Section E
- [ ] SSH to droplet as root: `ssh root@<DROPLET_IP>`
- [ ] Download and run the bootstrap script:
  ```bash
  curl -o setup_droplet.sh \
    https://raw.githubusercontent.com/cryptominer17/genai-demo/main/deployment/scripts/setup_droplet.sh \
    && bash setup_droplet.sh
  ```
- [ ] Verify bootstrap completed successfully:
  ```bash
  systemctl status nginx          # should show "active (running)"
  id streamlit                    # should print streamlit uid/gid
  ls /opt/fi-genai-poc-platform   # directory should exist (may be empty)
  ```
- [ ] Note the SSH public key printed at the end of the setup script — you will paste it into GitHub in Section B

---

## Section B: GitHub Repository

- [ ] Fork or clone the repository: https://github.com/cryptominer17/genai-demo
- [ ] Verify all expected top-level directories are present:
  - `README.md`, `.github/`, `apps/`, `shared/`, `deployment/`, `docs/`
- [ ] Add SSH deploy key to repo:
  1. Go to repository → Settings → Deploy Keys → Add deploy key
  2. Title: `fi-genai-poc-platform droplet`
  3. Key: paste the public key printed by the bootstrap script
  4. Check "Allow write access" → click Add key
- [ ] Add GitHub Actions secrets (Settings → Secrets and variables → Actions → New repository secret):
  - [ ] `DROPLET_IP` — your droplet's static IP address (e.g. `167.99.12.34`)
  - [ ] `DROPLET_SSH_KEY` — contents of `/home/streamlit/.ssh/id_ed25519` on the droplet (private key, multi-line)
  - [ ] `DROPLET_USER` — value: `streamlit`
  - [ ] `SMTP_PASSWORD` — Gmail App Password generated in Section D (16 characters, no spaces)

---

## Section C: Anthropic API

- [ ] Log in or create an account at https://console.anthropic.com
- [ ] Create a new API key (or locate an existing one with sufficient credits)
- [ ] Copy the key — it begins with `sk-ant-` and will not be shown again after creation
- [ ] Verify the account has at least a few dollars of credits available for demo usage
- [ ] Store the key somewhere secure (1Password, secrets manager) — you will paste it into `.env` in Section E

---

## Section D: Email (SMTP) Setup

The platform sends deployment notifications via Gmail SMTP. This requires a Gmail App Password, not your regular Gmail password.

- [ ] Log in to the Gmail account you want to use as the sender
- [ ] Enable 2-Factor Authentication if not already enabled: Google Account → Security → 2-Step Verification
- [ ] Generate an App Password: Google Account → Security → App Passwords
  - Select app: Mail
  - Select device: Other (custom name) → type `fi-genai-poc`
  - Click Generate → copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
- [ ] Test SMTP connectivity from your local machine:
  ```bash
  python3 -c "
  import smtplib
  s = smtplib.SMTP('smtp.gmail.com', 587)
  s.starttls()
  s.login('<your-gmail>', '<app-password-no-spaces>')
  print('SMTP OK')
  s.quit()
  "
  ```
  Expected output: `SMTP OK`
- [ ] Note the App Password (remove spaces before using it in `.env`)

---

## Section E: Droplet Configuration

- [ ] SSH as the streamlit user: `ssh streamlit@<DROPLET_IP>`
- [ ] Clone the repository into the app directory:
  ```bash
  git clone https://github.com/cryptominer17/genai-demo.git /opt/fi-genai-poc-platform
  ```
- [ ] Navigate to the app directory:
  ```bash
  cd /opt/fi-genai-poc-platform
  ```
- [ ] Create the `.env` file using `.env.example` as a template:
  ```bash
  cp .env.example .env
  nano .env
  ```
- [ ] Fill in all required values in `.env`:
  - [ ] `ANTHROPIC_API_KEY` — from Section C
  - [ ] `STREAMLIT_USERNAME` — choose a login username (e.g. `admin`)
  - [ ] `STREAMLIT_PASSWORD` — choose a strong password
  - [ ] `ENVIRONMENT` — set to `prod`
  - [ ] `EMAIL_RECIPIENT` — email address to receive deployment notifications (e.g. `shouvik.pradhan@gmail.com`)
  - [ ] `SMTP_SERVER` — `smtp.gmail.com`
  - [ ] `SMTP_PORT` — `587`
  - [ ] `SMTP_USERNAME` — Gmail sender address
  - [ ] `SMTP_PASSWORD` — App Password from Section D (no spaces)
- [ ] Save and close the file (`Ctrl+X`, `Y`, `Enter` in nano)
- [ ] Verify `.env` is git-ignored (must not be committed to GitHub):
  ```bash
  git -C /opt/fi-genai-poc-platform check-ignore .env
  ```
  Expected output: `.env`
- [ ] Confirm all vars loaded correctly:
  ```bash
  grep -c "=" /opt/fi-genai-poc-platform/.env
  ```
  Expected: `9` (one line per variable)

---

## Section F: Systemd and Nginx

Run all commands as a user with sudo privileges (the `streamlit` user has sudo configured by the bootstrap script).

- [ ] Copy all three systemd service files:
  ```bash
  sudo cp /opt/fi-genai-poc-platform/deployment/systemd/*.service /etc/systemd/system/
  ```
- [ ] Verify all three were copied:
  ```bash
  ls /etc/systemd/system/streamlit-*.service
  ```
  Expected: `streamlit-doc-intelligence.service`, `streamlit-data-qa.service`, `streamlit-report-generator.service`
- [ ] Copy nginx configuration:
  ```bash
  sudo cp /opt/fi-genai-poc-platform/deployment/nginx.conf /etc/nginx/sites-available/fi-genai-poc
  ```
- [ ] Enable the nginx site:
  ```bash
  sudo ln -s /etc/nginx/sites-available/fi-genai-poc /etc/nginx/sites-enabled/
  ```
- [ ] Remove the default nginx site (avoids port 80 conflict):
  ```bash
  sudo rm -f /etc/nginx/sites-enabled/default
  ```
- [ ] Test nginx configuration for syntax errors:
  ```bash
  sudo nginx -t
  ```
  Expected: `syntax is ok` and `test is successful`
- [ ] Restart nginx:
  ```bash
  sudo systemctl restart nginx
  ```
- [ ] Reload systemd to pick up the new service files:
  ```bash
  sudo systemctl daemon-reload
  ```
- [ ] Enable services to start on boot:
  ```bash
  sudo systemctl enable streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
  ```
- [ ] Verify services are enabled:
  ```bash
  systemctl is-enabled streamlit-doc-intelligence
  systemctl is-enabled streamlit-data-qa
  systemctl is-enabled streamlit-report-generator
  ```
  Expected: `enabled` for each

---

## Pre-Deploy Final Check

Before running `deploy.sh`, confirm:

- [ ] You can SSH as `streamlit@<DROPLET_IP>` without a password prompt
- [ ] `/opt/fi-genai-poc-platform/.env` exists and has all 9 variables
- [ ] `sudo nginx -t` passes
- [ ] GitHub secrets DROPLET_IP, DROPLET_SSH_KEY, DROPLET_USER, SMTP_PASSWORD are all set
- [ ] Anthropic API key is valid and has credits

You are ready to deploy. Proceed to `docs/POST_DEPLOYMENT_CHECKLIST.md` after running `deploy.sh`.
