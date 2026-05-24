# Post-Deployment Checklist — FI GenAI PoC Platform

Run through these checks immediately after `deploy.sh` completes for the first time.
All commands run on the droplet unless noted as "from browser" or "from local."

---

## Section A: Services Running

SSH to droplet: `ssh streamlit@<DROPLET_IP>`

- [ ] Check Document Intelligence service:
  ```bash
  systemctl is-active streamlit-doc-intelligence
  ```
  Expected: `active`

- [ ] Check Data Q&A service:
  ```bash
  systemctl is-active streamlit-data-qa
  ```
  Expected: `active`

- [ ] Check Report Generator service:
  ```bash
  systemctl is-active streamlit-report-generator
  ```
  Expected: `active`

- [ ] Run the automated health check script:
  ```bash
  bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh
  ```
  Expected: all three apps reported as healthy (green output, no failures)

- [ ] Check nginx is running:
  ```bash
  systemctl is-active nginx
  ```
  Expected: `active`

---

## Section B: Apps Accessible

**Direct port tests** (on droplet — confirms apps are up before nginx):

- [ ] `curl -f http://localhost:8501/` — should return HTML (Document Intelligence)
- [ ] `curl -f http://localhost:8502/` — should return HTML (Data Q&A)
- [ ] `curl -f http://localhost:8503/` — should return HTML (Report Generator)

**Via nginx** (from any machine with internet access — replace `<DROPLET_IP>`):

- [ ] `curl -f http://<DROPLET_IP>/Document_AI/` — should return HTML
- [ ] `curl -f http://<DROPLET_IP>/Text_to_SQL/` — should return HTML
- [ ] `curl -f http://<DROPLET_IP>/BI_Dashboard/` — should return HTML

**Health endpoint**:
- [ ] `curl http://<DROPLET_IP>/health`
  Expected response body: `OK` (this endpoint returns the string "OK", not "healthy")

**Root redirect**:
- [ ] `curl -I http://<DROPLET_IP>/`
  Expected: `302 Found` with `Location: /Document_AI/`

---

## Section C: Authentication

From a browser on your local machine:

- [ ] Open `http://<DROPLET_IP>/Document_AI` in browser
- [ ] Verify a login form appears (not a blank page or error)
- [ ] Enter the `STREAMLIT_USERNAME` and `STREAMLIT_PASSWORD` values from `.env`
- [ ] Verify the main Document Intelligence app loads after login
- [ ] Verify a logout button is visible in the app header or sidebar
- [ ] Log out, then attempt login with a wrong password
  - Expected: error message displayed, access denied
- [ ] Repeat login test for the other two apps:
  - [ ] `http://<DROPLET_IP>/Text_to_SQL`
  - [ ] `http://<DROPLET_IP>/BI_Dashboard`

---

## Section D: LLM Integration

These tests confirm Claude API connectivity is working end-to-end.

**Document Intelligence** (`http://<DROPLET_IP>/Document_AI`):
- [ ] After login, select `expense_report_q1_2024.txt` from the document list
- [ ] Click "Analyze Document" (or equivalent primary action button)
- [ ] Expected: Claude response appears within 10–30 seconds — not a timeout or API error message
- [ ] Verify the response contains meaningful text (not an empty box)

**Data Q&A** (`http://<DROPLET_IP>/Text_to_SQL`):
- [ ] After login, type `Show total sales by region` in the query input
- [ ] Click submit / press Enter
- [ ] Expected: pandas-generated code is displayed and query results appear
- [ ] Verify a chart or data table renders (not an error message)

**Report Generator** (`http://<DROPLET_IP>/BI_Dashboard`):
- [ ] After login, select "Q1 2024 KPI Summary" from the report selector
- [ ] Click "Generate Report"
- [ ] Expected: formatted report text appears within 10–30 seconds
- [ ] Verify charts or visualizations render alongside the report text

---

## Section E: Logging

- [ ] List log files (should exist after first run):
  ```bash
  ls /var/log/streamlit/
  ```
  Expected files: `doc-intelligence.log`, `doc-intelligence-error.log`, `data-qa.log`, `data-qa-error.log`, `report-generator.log`, `report-generator-error.log`, `deploy.log`

- [ ] Check deployment log for the most recent run:
  ```bash
  tail -20 /var/log/streamlit/deploy.log
  ```
  Expected: recent timestamp, no FAILED or ERROR lines

- [ ] Check for startup errors in Document Intelligence:
  ```bash
  journalctl -u streamlit-doc-intelligence -n 20 --no-pager
  ```
  Expected: no CRITICAL or traceback errors in the last 20 lines

- [ ] Spot-check the other two services:
  ```bash
  journalctl -u streamlit-data-qa -n 10 --no-pager
  journalctl -u streamlit-report-generator -n 10 --no-pager
  ```

- [ ] Check nginx access log is populating:
  ```bash
  tail -5 /var/log/nginx/fi-genai-poc-access.log
  ```
  Expected: entries from your recent browser/curl tests

---

## Section F: CI/CD Pipeline

This confirms that GitHub Actions automated deployments work correctly.

- [ ] From your local machine, push a minor change to the `main` branch:
  ```bash
  # Example: add a blank line to README
  echo "" >> README.md
  git add README.md
  git commit -m "test: ci/cd pipeline verification"
  git push origin main
  ```

- [ ] Go to https://github.com/cryptominer17/genai-demo/actions
- [ ] Verify the "Deploy to Digital Ocean Droplet" workflow was triggered (should appear within 30 seconds)
- [ ] Wait for the workflow to complete — expected: green checkmark on all steps
  - Step: Set up SSH
  - Step: Deploy to droplet
  - Step: Verify app health (wait for startup)
  - Step: Notify on success

- [ ] Verify deployment notification email received at `shouvik.pradhan@gmail.com`
  - Subject should reference "SUCCESS" and "Deployment completed successfully"

- [ ] After workflow completes, verify all three apps are still accessible via browser

- [ ] Check deploy log on droplet to confirm CI/CD-triggered deploy is recorded:
  ```bash
  tail -20 /var/log/streamlit/deploy.log
  ```

---

## All Clear Criteria

The deployment is considered healthy when all of the following are true:

1. All three `systemctl is-active` checks return `active`
2. All three nginx proxy routes return HTML
3. Login works with correct credentials, fails with wrong credentials
4. At least one LLM call (any app) returns a Claude response
5. GitHub Actions workflow completes green and email notification arrives

If any check fails, see `docs/ROLLBACK_GUIDE.md` for remediation steps.
