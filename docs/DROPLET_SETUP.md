# Droplet Setup Checklist — fi-genai-poc-platform

Step-by-step guide for provisioning and configuring the Digital Ocean droplet
that hosts the FI GenAI PoC Platform multi-app Streamlit deployment.

Work through each section in order. Check off items as you complete them.

---

## 1. Create the Digital Ocean Droplet

- [ ] Log in to [Digital Ocean](https://cloud.digitalocean.com)
- [ ] Click **Create → Droplets**
- [ ] Choose image: **Ubuntu 22.04 (LTS) x64**
- [ ] Choose plan: **Basic — Regular SSD — 2 GB RAM / 1 vCPU / 50 GB disk ($12/mo)**
- [ ] Choose region: **New York 1** or **Virginia (AMS3)** — pick whichever is closest to your users
- [ ] Under **Authentication**, choose **SSH Key** and add your local machine's public key
- [ ] Set hostname: `fi-genai-poc-platform`
- [ ] Click **Create Droplet** and wait for provisioning (~60 seconds)
- [ ] Note the droplet's **public IPv4 address** — you'll need it in later steps

---

## 2. First SSH Login as Root

- [ ] Open a terminal on your local machine
- [ ] Connect as root:
  ```bash
  ssh root@<DROPLET_IP>
  ```
- [ ] Accept the host fingerprint prompt (type `yes`)
- [ ] Confirm you are logged in — you should see the Ubuntu welcome banner

---

## 3. Run the Bootstrap Script

Choose **one** of the two methods below.

### Method A — curl (recommended if the script is in a public/accessible repo)

```bash
curl -fsSL https://raw.githubusercontent.com/<YOUR_ORG>/<YOUR_REPO>/main/deployment/scripts/setup_droplet.sh | bash
```

### Method B — scp (copy from your local machine first)

From your **local** terminal (not the droplet):
```bash
scp deployment/scripts/setup_droplet.sh root@<DROPLET_IP>:/root/setup_droplet.sh
```

Then back on the droplet:
```bash
chmod +x /root/setup_droplet.sh
bash /root/setup_droplet.sh
```

- [ ] Script ran without errors (watch for any red `ERROR` lines)
- [ ] Script printed the SSH public key at the end — **copy it now**

---

## 4. Verify the Setup

SSH back into the droplet (if you exited) and run these checks:

- [ ] **streamlit user exists:**
  ```bash
  id streamlit
  # Expected: uid=... gid=... groups=...,sudo
  ```

- [ ] **App directory exists and is owned by streamlit:**
  ```bash
  ls -ld /opt/fi-genai-poc-platform
  # Expected: drwxr-xr-x ... streamlit streamlit ...
  ```

- [ ] **Log directory exists and is owned by streamlit:**
  ```bash
  ls -ld /var/log/streamlit
  # Expected: drwxr-xr-x ... streamlit streamlit ...
  ```

- [ ] **nginx is running:**
  ```bash
  systemctl status nginx
  # Expected: active (running)
  ```

- [ ] **UFW is active with correct rules:**
  ```bash
  ufw status verbose
  # Expected: 22/tcp, 80/tcp, 443/tcp ALLOW
  ```

- [ ] **SSH key was generated:**
  ```bash
  ls -la /home/streamlit/.ssh/
  # Expected: id_ed25519 (600) and id_ed25519.pub (644)
  ```

---

## 5. Add SSH Public Key to GitHub Deploy Keys

- [ ] Copy the public key (printed at end of bootstrap script, or re-display it):
  ```bash
  cat /home/streamlit/.ssh/id_ed25519.pub
  ```
- [ ] Go to your GitHub repository
- [ ] Navigate to **Settings → Deploy keys → Add deploy key**
- [ ] Title: `fi-genai-poc-platform droplet`
- [ ] Paste the public key into the **Key** field
- [ ] Check **Allow write access** only if the droplet needs to push back to the repo (typically not needed — leave unchecked for read-only deploys)
- [ ] Click **Add key**
- [ ] Test the connection from the droplet:
  ```bash
  sudo -u streamlit ssh -T git@github.com
  # Expected: Hi <org/user>! You've successfully authenticated...
  ```

---

## 6. Record the Droplet IP for GitHub Secrets

The GitHub Actions deployment workflow needs the droplet's IP address.

- [ ] Get the droplet IP on the droplet:
  ```bash
  hostname -I | awk '{print $1}'
  ```
  Or check the Digital Ocean dashboard.

- [ ] In GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**
- [ ] Add the following secrets:

  | Secret name       | Value                                  |
  |-------------------|----------------------------------------|
  | `DROPLET_HOST`    | `<DROPLET_IP>`                         |
  | `DROPLET_USER`    | `streamlit`                            |
  | `DROPLET_SSH_KEY` | Contents of your **local** private key |

- [ ] Consider assigning a **Reserved IP** (static IP) in Digital Ocean so the IP never changes if you rebuild the droplet

---

## 7. Create the `.env` File on the Droplet

Application secrets are never committed to the repo. They live only on the droplet.

- [ ] SSH into the droplet as (or switch to) the streamlit user:
  ```bash
  sudo -i -u streamlit
  ```
- [ ] Create the env file in the app directory:
  ```bash
  nano /opt/fi-genai-poc-platform/.env
  ```
- [ ] Add the required variables (examples — replace with real values):
  ```env
  # Snowflake connection
  SNOWFLAKE_ACCOUNT=<your_account>
  SNOWFLAKE_USER=<your_user>
  SNOWFLAKE_PASSWORD=<your_password>
  SNOWFLAKE_WAREHOUSE=<your_warehouse>
  SNOWFLAKE_DATABASE=<your_database>
  SNOWFLAKE_SCHEMA=<your_schema>

  # AWS credentials (if applicable)
  AWS_ACCESS_KEY_ID=<your_key_id>
  AWS_SECRET_ACCESS_KEY=<your_secret>
  AWS_DEFAULT_REGION=us-east-1

  # App settings
  APP_ENV=production
  LOG_LEVEL=INFO
  ```
- [ ] Save the file (`Ctrl+O`, `Enter`, `Ctrl+X` in nano)
- [ ] Lock down permissions:
  ```bash
  chmod 600 /opt/fi-genai-poc-platform/.env
  ```

---

## 8. What NOT to Do

These are the guardrails. Don't skip this section.

- [ ] **Never commit `.env`** to the repository. Confirm `.env` is in `.gitignore`.
- [ ] **Never run Streamlit apps as root.** The `streamlit` user exists for this reason.
- [ ] **Never open all ports.** UFW is configured for 22, 80, 443 only. Don't add `ufw allow` for app ports (8501, etc.) — route traffic through nginx instead.
- [ ] **Never store passwords in plain text in scripts.** All secrets go in `.env` or GitHub Secrets.
- [ ] **Never disable UFW** to "fix" a connection issue. Debug the rule instead.
- [ ] **Don't run `apt-get upgrade` on the droplet without a maintenance window** — package upgrades can restart services and temporarily disrupt running apps.
- [ ] **Don't share the `DROPLET_SSH_KEY` GitHub secret** with anyone who doesn't need deploy access.
- [ ] **Don't reuse the droplet's deploy key** as your personal GitHub SSH key — keep them separate.

---

*Last updated: 2026-05-24*
