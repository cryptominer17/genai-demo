# GitHub Secrets & Deploy Keys Setup

This guide covers everything you need to configure before the GitHub Actions CI/CD pipeline (`deploy.yml`) will work correctly.

---

## 1. Required Secrets

| Secret name | Purpose |
|---|---|
| `DROPLET_IP` | Public IP address of your DigitalOcean droplet |
| `DROPLET_SSH_KEY` | Private SSH key the runner uses to connect to the droplet |
| `DROPLET_USER` | SSH login user on the droplet (`streamlit`) |
| `SMTP_PASSWORD` | Gmail App Password used by `notify.py` to send emails |

---

## 2. How to Add Secrets in GitHub

1. Open your repository: `https://github.com/cryptominer17/genai-demo`
2. Click **Settings** (top navigation bar)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the **Name** and **Secret** value, then click **Add secret**
6. Repeat for each secret below

---

## 3. How to Get Each Value

### `DROPLET_IP`
- Log in to [DigitalOcean](https://cloud.digitalocean.com/)
- Go to **Droplets** in the left sidebar
- Find your droplet — the public IPv4 address is displayed in the list
- Copy it (e.g. `143.198.xxx.xxx`)

---

### `DROPLET_SSH_KEY`
This is the **private** key for the `streamlit` user on your droplet.

1. SSH into your droplet as root or a sudo user
2. Switch to the streamlit user: `sudo -u streamlit bash`
3. Print the private key:
   ```bash
   cat /home/streamlit/.ssh/id_ed25519
   ```
4. Copy the **entire output** including the header and footer lines:
   ```
   -----BEGIN OPENSSH PRIVATE KEY-----
   ...
   -----END OPENSSH PRIVATE KEY-----
   ```
5. Paste the full multi-line content as the secret value in GitHub — paste it as-is, no modifications

> **Note:** If this key doesn't exist yet, generate it on the droplet:
> ```bash
> sudo -u streamlit ssh-keygen -t ed25519 -C "github-actions-deploy" -f /home/streamlit/.ssh/id_ed25519 -N ""
> ```
> Then add the public key to `authorized_keys` (see Section 4).

---

### `DROPLET_USER`
- The value is simply: `streamlit`
- This is the non-root deployment user that owns `/opt/fi-genai-poc-platform`

---

### `SMTP_PASSWORD`
This must be a **Gmail App Password** — not your regular Gmail password.

**Prerequisites:** Gmail 2-Step Verification must be enabled.

**Steps to generate an App Password:**
1. Go to your Google Account: [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Under **"How you sign in to Google"**, click **2-Step Verification**
3. Scroll to the bottom and click **App passwords**
4. Under "Select app", choose **Mail**; under "Select device", choose **Other (custom name)**
5. Type a name like `fi-genai-deploy` and click **Generate**
6. Copy the 16-character password shown (spaces don't matter; you can include or remove them)
7. Use this as the `SMTP_PASSWORD` secret value

> Also update `SMTP_USERNAME` in your `.env` file on the droplet with the Gmail address this App Password belongs to.

---

## 4. Add the Public Key to GitHub Deploy Keys

This allows the droplet to pull from the private GitHub repository.

1. On the droplet, print the **public** key:
   ```bash
   cat /home/streamlit/.ssh/id_ed25519.pub
   ```
2. Copy the output (one line, starts with `ssh-ed25519 ...`)
3. In GitHub, go to **Settings** → **Deploy keys** → **Add deploy key**
4. Title: `fi-genai-droplet-deploy`
5. Paste the public key into the **Key** field
6. Check **Allow write access** (required for `git pull` to work via deploy key)
7. Click **Add key**

---

## 5. Verifying the Setup

### Trigger the workflow
Push any change to the `main` branch:
```bash
git commit --allow-empty -m "test: trigger CI/CD pipeline"
git push origin main
```

### View workflow logs
1. Go to your repo on GitHub
2. Click the **Actions** tab
3. Click the latest workflow run to see each step's output
4. If a step fails, expand it to see the error message

### Check droplet logs
SSH into the droplet and inspect the deploy log:
```bash
tail -f /var/log/streamlit/deploy.log
```

### Check service status
```bash
sudo systemctl status streamlit-doc-intelligence
sudo systemctl status streamlit-data-qa
sudo systemctl status streamlit-report-generator
```

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Permission denied (publickey)` | Wrong or missing SSH key | Re-check `DROPLET_SSH_KEY` secret and `authorized_keys` on droplet |
| `Host key verification failed` | `ssh-keyscan` step failed | Check `DROPLET_IP` secret is correct |
| `SMTP authentication failed` | Wrong App Password | Regenerate Gmail App Password |
| Health check fails on port 850x | Service crashed | Check `journalctl -u streamlit-doc-intelligence -n 50` |
| `.env file is missing` | `.env` not on droplet | SSH to droplet, create `/opt/fi-genai-poc-platform/.env` from `.env.example` |
