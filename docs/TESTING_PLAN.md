# Testing Plan — FI GenAI PoC Platform

This document describes the four testing phases that should be completed before
presenting the platform to stakeholders. Each phase builds on the previous one.

---

## Phase 1: Local Development Testing

**Goal**: Confirm the code runs correctly on a developer's machine before pushing to the droplet.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/cryptominer17/genai-demo.git
   cd genai-demo
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate          # Linux/Mac
   # or: venv\Scripts\activate       # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r shared/requirements.txt
   ```

4. Create a local `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env — set ANTHROPIC_API_KEY, STREAMLIT_USERNAME, STREAMLIT_PASSWORD
   # Set ENVIRONMENT=dev
   ```

### App Launch Tests

Run each app individually and confirm it starts without errors:

```bash
# Terminal 1
python -m streamlit run apps/document_intelligence/streamlit_app.py --server.port 8501

# Terminal 2
python -m streamlit run apps/data_qa/streamlit_app.py --server.port 8502

# Terminal 3
python -m streamlit run apps/report_generator/streamlit_app.py --server.port 8503
```

Expected: Each app opens in browser, login form appears, no import errors in terminal output.

### Mock Data Validation

- [ ] Document Intelligence: open `shared/mock_data/documents/` — verify at least 3 `.txt` files present and readable
- [ ] Data Q&A: open `shared/mock_data/datasets/` — verify CSV files load (check headers, row counts)
- [ ] Report Generator: open `shared/mock_data/bi_data/` — verify data files present

### Auth Test (Local)

- [ ] Login with correct STREAMLIT_USERNAME / STREAMLIT_PASSWORD → app loads
- [ ] Login with wrong password → error message shown, app blocked
- [ ] Logout → returns to login screen
- [ ] After logout, direct URL navigation → redirected to login

### LLM Test (Local)

- [ ] Document Intelligence: run an analysis → Claude response returned (not timeout)
- [ ] Data Q&A: submit a natural language query → results rendered
- [ ] Report Generator: generate a report → formatted text returned

---

## Phase 2: Droplet Pre-Deploy Testing

**Goal**: Validate the droplet environment is correctly configured before the first `deploy.sh` run.

### Automated Verification

If a `verify_droplet.sh` script is available:
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/verify_droplet.sh
```

### Manual Checks

- [ ] Python version is 3.10+:
  ```bash
  python3 --version
  ```

- [ ] pip is available:
  ```bash
  python3 -m pip --version
  ```

- [ ] Virtual environment can be created:
  ```bash
  python3 -m venv /tmp/test-venv && echo "venv OK" && rm -rf /tmp/test-venv
  ```

- [ ] Dependency install test (dry run):
  ```bash
  pip install --dry-run -r /opt/fi-genai-poc-platform/shared/requirements.txt 2>&1 | tail -5
  ```

- [ ] `.env` validation — confirm all 9 required variables are set:
  ```bash
  python3 -c "
  import os
  from dotenv import load_dotenv
  load_dotenv('/opt/fi-genai-poc-platform/.env')
  required = ['ANTHROPIC_API_KEY','STREAMLIT_USERNAME','STREAMLIT_PASSWORD',
              'ENVIRONMENT','EMAIL_RECIPIENT','SMTP_SERVER','SMTP_PORT',
              'SMTP_USERNAME','SMTP_PASSWORD']
  missing = [v for v in required if not os.getenv(v)]
  print('Missing:', missing if missing else 'None — all vars present')
  "
  ```

- [ ] Systemd service file syntax check:
  ```bash
  systemd-analyze verify /etc/systemd/system/streamlit-doc-intelligence.service
  systemd-analyze verify /etc/systemd/system/streamlit-data-qa.service
  systemd-analyze verify /etc/systemd/system/streamlit-report-generator.service
  ```
  Expected: no output (warnings/errors would print here)

- [ ] Nginx config syntax:
  ```bash
  sudo nginx -t
  ```

- [ ] Port availability (nothing else using 8501–8503):
  ```bash
  ss -tlnp | grep -E '850[123]'
  ```
  Expected: no output before services are started

---

## Phase 3: End-to-End Functional Testing

**Goal**: Validate every user-facing feature of each app on the deployed droplet.

### Document Intelligence (`http://<DROPLET_IP>/Document_AI`)

| # | Test Scenario | Steps | Expected Result |
|---|--------------|-------|----------------|
| 1 | Load document | Select any document from list | Document name shown, content preview if applicable |
| 2 | Summary analysis | Select document → choose "Summary" mode → click Analyze | Paragraph summary returned by Claude |
| 3 | Extraction | Select document → choose "Extract" mode → click Analyze | Structured data (dates, amounts, names) extracted |
| 4 | Q&A mode | Select document → choose "Q&A" → type a question → submit | Claude answers based on document content |
| 5 | Risk flags | Select document → choose "Risk" mode → click Analyze | Risk items or "no issues found" response |
| 6 | Error state | Click Analyze without selecting a document | Error message shown, no crash |

### Data Q&A (`http://<DROPLET_IP>/Text_to_SQL`)

| # | Test Scenario | Steps | Expected Result |
|---|--------------|-------|----------------|
| 1 | Load dataset | Select "Sales" dataset from dropdown | Dataset info shown (row count, columns) |
| 2 | Natural language query | Type "Show total sales by region" → submit | Table or chart with aggregated data |
| 3 | Chart generation | Type "Show monthly trend as a line chart" → submit | Line chart rendered |
| 4 | Invalid query | Type "asdfghjkl" → submit | Graceful error message, no crash |
| 5 | Switch dataset | Change dataset dropdown → rerun a query | Results reflect new dataset |
| 6 | Chat mode | If multi-turn supported: ask follow-up question | Response references prior context |

### Report Generator (`http://<DROPLET_IP>/BI_Dashboard`)

| # | Test Scenario | Steps | Expected Result |
|---|--------------|-------|----------------|
| 1 | KPI report | Select "Q1 2024 KPI Summary" → Generate | Formatted KPI report text with metrics |
| 2 | Forecast report | Select forecast report type → Generate | Forward-looking narrative with numbers |
| 3 | Segmentation report | Select customer/segment report → Generate | Segment breakdown in report body |
| 4 | Download button | Generate any report → click Download | File downloaded to browser (PDF or text) |
| 5 | Chart rendering | Generate a report with charts enabled | At least one chart renders inline |

### Test Results Template

Copy this table into a spreadsheet or doc when running tests:

```
| Date       | Tester | App                  | Test # | Scenario           | Pass/Fail | Notes              |
|------------|--------|----------------------|--------|--------------------|-----------|--------------------|
| YYYY-MM-DD |        | Document Intelligence | 1      | Load document      |           |                    |
| YYYY-MM-DD |        | Document Intelligence | 2      | Summary analysis   |           |                    |
| YYYY-MM-DD |        | Document Intelligence | 3      | Extraction         |           |                    |
| YYYY-MM-DD |        | Document Intelligence | 4      | Q&A mode           |           |                    |
| YYYY-MM-DD |        | Document Intelligence | 5      | Risk flags         |           |                    |
| YYYY-MM-DD |        | Document Intelligence | 6      | Error state        |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 1      | Load dataset       |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 2      | NL query           |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 3      | Chart generation   |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 4      | Invalid query      |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 5      | Switch dataset     |           |                    |
| YYYY-MM-DD |        | Data Q&A              | 6      | Chat mode          |           |                    |
| YYYY-MM-DD |        | Report Generator      | 1      | KPI report         |           |                    |
| YYYY-MM-DD |        | Report Generator      | 2      | Forecast report    |           |                    |
| YYYY-MM-DD |        | Report Generator      | 3      | Segmentation       |           |                    |
| YYYY-MM-DD |        | Report Generator      | 4      | Download button    |           |                    |
| YYYY-MM-DD |        | Report Generator      | 5      | Chart rendering    |           |                    |
```

---

## Phase 4: CI/CD Pipeline Testing

**Goal**: Confirm the automated deployment pipeline is reliable end-to-end.

### Push Test

1. Make a trivial change on `main` branch and push:
   ```bash
   echo "# ci/cd test $(date)" >> README.md
   git add README.md && git commit -m "test: ci/cd verification" && git push origin main
   ```

2. Navigate to https://github.com/cryptominer17/genai-demo/actions

### Workflow Trigger Verification

- [ ] Workflow "Deploy to Digital Ocean Droplet" appears within 60 seconds of push
- [ ] All four steps appear in the workflow log:
  - Set up SSH
  - Deploy to droplet
  - Verify app health (wait for startup)
  - Notify on success

### Deployment Script Execution

- [ ] On the droplet, confirm deploy script ran:
  ```bash
  tail -20 /var/log/streamlit/deploy.log
  ```
  Expected: log entries matching the push timestamp

### Health Check Assertions

- [ ] Workflow step "Verify app health" completes successfully (green)
- [ ] On droplet, all three services still active after deploy:
  ```bash
  systemctl is-active streamlit-doc-intelligence streamlit-data-qa streamlit-report-generator
  ```

### Email Notification Verification

- [ ] Email arrives at `shouvik.pradhan@gmail.com` with subject containing "SUCCESS"
- [ ] Email body references "All 3 apps are running"

### Rollback Scenario

Test what happens if `deploy.sh` fails partway through:

1. Temporarily introduce a syntax error in a non-critical file (e.g., add an invalid line to a config)
2. Push to main — workflow should trigger
3. Expected: deploy fails, workflow step goes red, "Notify on failure" step runs
4. Verify email arrives with "FAILURE" subject
5. Verify apps are still accessible (deploy failure should not take down running services)
6. Revert the syntax error, push again — verify clean recovery

### Recovery Time Objective

- Target: a push to `main` results in a running updated deployment within 3 minutes
- Measure: time from push to all three `systemctl is-active` checks passing
