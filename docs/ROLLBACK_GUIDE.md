# Rollback Guide — FI GenAI PoC Platform

Use this guide when a deployment breaks something. Each scenario is independent —
jump directly to the one that matches your situation.

---

## Quick Decision Tree

```
Is the browser showing an error?
│
├── 502 Bad Gateway
│   ├── Is nginx running?  →  sudo systemctl status nginx
│   │   ├── No  →  sudo systemctl start nginx
│   │   └── Yes →  Are the apps running?  →  systemctl is-active streamlit-doc-intelligence
│   │               ├── No  →  See Scenario 2 (service won't start)
│   │               └── Yes →  sudo nginx -t  →  fix config if invalid
│   └── → See Scenario 3 (Nginx broke)
│
├── 404 Not Found on /Document_AI, /Text_to_SQL, /BI_Dashboard
│   └── Nginx site not enabled  →  check /etc/nginx/sites-enabled/
│
├── Login page appears but LLM calls fail
│   └── Check .env ANTHROPIC_API_KEY is set correctly
│       journalctl -u streamlit-doc-intelligence -n 30
│
├── Everything was fine, then a push broke it
│   └── See Scenario 1 (new deployment broke an app)
│
└── Can't reach the droplet at all
    └── See Scenario 4 (full disaster)
```

---

## Scenario 1: New Deployment Broke an App

A recent push to `main` triggered a deploy that broke one or more apps.

**Step 1: Identify the last good commit**
```bash
ssh streamlit@<DROPLET_IP>
cd /opt/fi-genai-poc-platform
git log --oneline -10
```
Note the hash of the last commit you know was working (e.g., `a3f8c12`).

**Step 2: Revert to that commit**
```bash
git checkout <commit-hash>
```
This puts the repo in "detached HEAD" state at the known-good commit.

**Step 3: Restart all services**
```bash
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

**Step 4: Verify recovery**
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh
```

**Step 5: Fix the broken code**
On your local machine:
- Identify the breaking change in the commit that failed
- Fix it in a new branch, test locally (Phase 1 of testing plan)
- Push the fix to `main` — this triggers a fresh deploy

**Step 6: Return to HEAD after fix is deployed**
```bash
git checkout main
git pull
```

---

## Scenario 2: Service Won't Start After Deploy

One or more systemd services fail to reach `active` state.

**Step 1: Check the error**
```bash
journalctl -u streamlit-doc-intelligence -n 50 --no-pager
```
Look for Python tracebacks, ImportError, FileNotFoundError, or permission errors.

**Common Fix A: .env file is missing or incomplete**
```bash
ls -la /opt/fi-genai-poc-platform/.env
```
If missing, recreate it:
```bash
cp /opt/fi-genai-poc-platform/.env.example /opt/fi-genai-poc-platform/.env
nano /opt/fi-genai-poc-platform/.env
# Fill in all values, then:
sudo systemctl restart streamlit-doc-intelligence
```

**Common Fix B: Virtual environment is broken or missing**
```bash
/opt/fi-genai-poc-platform/venv/bin/python --version
```
If this fails, rebuild the venv:
```bash
cd /opt/fi-genai-poc-platform
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r shared/requirements.txt
deactivate
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

**Common Fix C: File permissions changed**
```bash
sudo chown -R streamlit:streamlit /opt/fi-genai-poc-platform
sudo chmod -R u+rX /opt/fi-genai-poc-platform
sudo systemctl restart streamlit-doc-intelligence
```

**Common Fix D: Port already in use**
```bash
ss -tlnp | grep 8501
# If something else is using 8501:
sudo kill $(lsof -t -i:8501)
sudo systemctl restart streamlit-doc-intelligence
```

---

## Scenario 3: Nginx Broke (502 or Config Errors)

Apps run fine on their direct ports but nginx returns errors.

**Step 1: Check config syntax**
```bash
sudo nginx -t
```
If this reports errors, the config file has a syntax problem. Compare against the repo version:
```bash
diff /etc/nginx/sites-available/fi-genai-poc /opt/fi-genai-poc-platform/deployment/nginx.conf
```
Restore from repo if needed:
```bash
sudo cp /opt/fi-genai-poc-platform/deployment/nginx.conf /etc/nginx/sites-available/fi-genai-poc
sudo nginx -t && sudo systemctl reload nginx
```

**Step 2: Reload if config is valid**
```bash
sudo nginx -t && sudo systemctl reload nginx
```

**Step 3: Confirm apps are actually listening**
```bash
curl http://localhost:8501/ || echo "8501 not responding"
curl http://localhost:8502/ || echo "8502 not responding"
curl http://localhost:8503/ || echo "8503 not responding"
```
If apps aren't responding, the issue is the services, not nginx — see Scenario 2.

**Step 4: Check nginx error log**
```bash
tail -30 /var/log/nginx/fi-genai-poc-error.log
```

**Step 5: Restart nginx**
```bash
sudo systemctl restart nginx
```

---

## Scenario 4: Full Disaster (Droplet Unreachable)

The droplet is down, destroyed, or unresponsive. You need to stand up a new one.

**Step 1: Create a new Digital Ocean droplet**
- Ubuntu 22.04 LTS, 2 GB RAM, Virginia region
- Hostname: `fi-genai-poc-platform`
- Note the new static IP

**Step 2: Run the bootstrap script on the new droplet**
```bash
ssh root@<NEW_DROPLET_IP>
curl -o setup_droplet.sh \
  https://raw.githubusercontent.com/cryptominer17/genai-demo/main/deployment/scripts/setup_droplet.sh \
  && bash setup_droplet.sh
```

**Step 3: Clone repo and restore .env**

The `.env` file is not in GitHub (by design — it contains secrets). You must recreate it.
If you saved the values elsewhere (1Password, secrets manager), use them now:
```bash
ssh streamlit@<NEW_DROPLET_IP>
git clone https://github.com/cryptominer17/genai-demo.git /opt/fi-genai-poc-platform
cp /opt/fi-genai-poc-platform/.env.example /opt/fi-genai-poc-platform/.env
nano /opt/fi-genai-poc-platform/.env
# Fill in all 9 variables
```

**Step 4: Complete setup**

Follow Sections E and F of `docs/PRE_DEPLOYMENT_CHECKLIST.md` from scratch.

**Step 5: Update GitHub secrets**

The new droplet has a different IP and a new SSH key:
- Update `DROPLET_IP` secret in GitHub with the new IP
- Update `DROPLET_SSH_KEY` secret with the new private key from `/home/streamlit/.ssh/id_ed25519`

**Step 6: Trigger a fresh deploy**
```bash
# From local machine — push any change to main
git commit --allow-empty -m "trigger: redeploy after droplet replacement"
git push origin main
```

**Step 7: Revert to last known good commit if current HEAD is bad**
```bash
ssh streamlit@<NEW_DROPLET_IP>
cd /opt/fi-genai-poc-platform
git log --oneline -10        # Identify last good commit
git checkout <good-commit>   # Check out known-good state
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
```

---

## Scenario 5: GitHub Actions Keeps Failing

Automated deploys are broken and you need to deploy manually while you fix the pipeline.

**Step 1: Disable the workflow temporarily**
1. Go to https://github.com/cryptominer17/genai-demo/actions
2. Click "Deploy to Digital Ocean Droplet"
3. Click the "..." menu → Disable workflow
   This prevents further failed runs while you investigate.

**Step 2: Deploy manually from the droplet**
```bash
ssh streamlit@<DROPLET_IP>
cd /opt/fi-genai-poc-platform
git pull origin main
bash deployment/scripts/deploy.sh
```

**Step 3: Diagnose the workflow failure**

Common causes:
- **SSH key mismatch**: The `DROPLET_SSH_KEY` secret doesn't match what's on the droplet. Re-export `/home/streamlit/.ssh/id_ed25519` and update the secret.
- **IP changed**: The `DROPLET_IP` secret is stale. Update it with the current droplet IP.
- **deploy.sh script error**: Check the workflow log for the exact error line. Test the script manually (Step 2) to reproduce locally.
- **Health check timing**: The 20-second sleep may be too short for slow startups. Edit `.github/workflows/deploy.yml` to increase the sleep value.

**Step 4: Re-enable the workflow**
After fixing the root cause:
1. Go to GitHub Actions → Deploy workflow → "..." menu → Enable workflow
2. Push a test commit to verify the fix

---

## General Recovery Commands Reference

```bash
# Restart all three apps at once
sudo systemctl restart streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator

# View last 50 lines from any service
journalctl -u streamlit-doc-intelligence -n 50 --no-pager
journalctl -u streamlit-data-qa -n 50 --no-pager
journalctl -u streamlit-report-generator -n 50 --no-pager

# Check all service statuses at once
systemctl status streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator --no-pager

# Force-stop a stuck service
sudo systemctl kill streamlit-doc-intelligence
sudo systemctl start streamlit-doc-intelligence

# Check disk space (low disk can cause silent failures)
df -h /opt

# Check memory
free -h
```
