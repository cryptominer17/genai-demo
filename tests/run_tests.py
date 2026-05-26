"""
tests/run_tests.py — Test runner for the FI GenAI PoC Platform.

Runs the full test suite via pytest, collects pass/fail/skip/error counts,
builds an HTML email report, and sends it via the existing SMTP setup.

Usage (on the droplet):
    cd /opt/fi-genai-poc-platform
    source venv/bin/activate
    python3 tests/run_tests.py

Exit codes:
    0 — all tests passed (or only skips)
    1 — one or more failures or errors

Environment variables (loaded from .env if present):
    DROPLET_IP        — used in report URLs
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_RECIPIENT
    ANTHROPIC_API_KEY — required for LLM tests; those are skipped if absent
"""

import os
import sys
import json
import smtplib
import subprocess
import tempfile
import traceback
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — ensure repo root is importable and .env is loaded
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
except ImportError:
    pass  # python-dotenv absent; rely on environment

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DROPLET_IP        = os.environ.get("DROPLET_IP", "157.230.82.180")
SMTP_SERVER       = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT         = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME     = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD     = os.environ.get("SMTP_PASSWORD", "")
EMAIL_RECIPIENT   = os.environ.get("EMAIL_RECIPIENT", "shouvik.pradhan@gmail.com")

TEST_MODULE       = str(REPO_ROOT / "tests" / "test_platform.py")
JSON_REPORT_FILE  = str(REPO_ROOT / "tests" / "_last_run.json")

APP_URLS = {
    "Landing Page":       f"http://{DROPLET_IP}/",
    "Document AI":        f"http://{DROPLET_IP}/Document_AI/",
    "Data Q&A":           f"http://{DROPLET_IP}/Text_to_SQL/",
    "Report Generator":   f"http://{DROPLET_IP}/BI_Dashboard/",
    "Admin Console":      f"http://{DROPLET_IP}/admin/",
}


# ===========================================================================
# Step 1 — Run pytest and capture JSON report
# ===========================================================================

def run_pytest() -> dict:
    """
    Invoke pytest with --json-report and return the parsed report dict.

    Falls back to a minimal error dict if pytest itself crashes.
    """
    json_path = JSON_REPORT_FILE

    cmd = [
        sys.executable, "-m", "pytest",
        TEST_MODULE,
        "-v",
        "--tb=short",
        "--json-report",
        f"--json-report-file={json_path}",
        "--json-report-indent=2",
        # Inject DROPLET_IP so HTTP tests can pick it up
        f"--env=DROPLET_IP={DROPLET_IP}",
    ]

    print(f"\n{'='*60}")
    print("FI GenAI PoC Platform — Test Suite")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,   # let output stream to console
            text=True,
        )
        exit_code = result.returncode
    except Exception as exc:
        print(f"[run_tests] pytest launch failed: {exc}")
        return _error_report(str(exc))

    # Parse JSON report
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            report = json.load(fh)
        report["_exit_code"] = exit_code
        return report
    except Exception as exc:
        print(f"[run_tests] Could not parse JSON report: {exc}")
        return _error_report(f"JSON report parse error: {exc}", exit_code=exit_code)


def _error_report(message: str, exit_code: int = 1) -> dict:
    return {
        "_exit_code": exit_code,
        "summary": {"passed": 0, "failed": 0, "error": 1, "skipped": 0, "total": 0},
        "tests": [],
        "_error_message": message,
    }


# ===========================================================================
# Step 2 — Build HTML email body
# ===========================================================================

def _outcome_style(outcome: str) -> tuple[str, str]:
    """Return (background_color, text) for a test outcome."""
    return {
        "passed":  ("#e8f5e9", "✅ PASSED"),
        "failed":  ("#ffebee", "❌ FAILED"),
        "error":   ("#fff3e0", "⚠️ ERROR"),
        "skipped": ("#f3f3f3", "⏭ SKIPPED"),
    }.get(outcome.lower(), ("#ffffff", outcome.upper()))


def build_html_report(report: dict, duration_secs: float) -> str:
    summary  = report.get("summary", {})
    tests    = report.get("tests", [])
    exit_code = report.get("_exit_code", 1)

    passed   = summary.get("passed", 0)
    failed   = summary.get("failed", 0)
    errors   = summary.get("error", 0)
    skipped  = summary.get("skipped", 0)
    total    = summary.get("total", 0) or len(tests)

    all_ok   = (failed == 0 and errors == 0)
    status_label = "ALL TESTS PASSED" if all_ok else "TESTS FAILED"
    status_color = "#2e7d32" if all_ok else "#c62828"
    status_bg    = "#e8f5e9" if all_ok else "#ffebee"
    status_icon  = "✅" if all_ok else "❌"
    timestamp    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # --- App URLs table ---
    app_rows_html = "\n".join(
        f'<tr>'
        f'<td style="padding:6px 12px;">{name}</td>'
        f'<td style="padding:6px 12px;"><a href="{url}" style="color:#1565c0;">{url}</a></td>'
        f'</tr>'
        for name, url in APP_URLS.items()
    )

    # --- Per-test rows ---
    test_rows_html = ""
    for t in tests:
        outcome  = t.get("outcome", "unknown")
        nodeid   = t.get("nodeid", "")
        duration = t.get("duration", 0.0)
        bg, label = _outcome_style(outcome)

        # Collapse long class prefix for readability
        short_id = nodeid.replace("tests/test_platform.py::", "")

        # Capture failure details
        longrepr = ""
        if outcome in ("failed", "error"):
            call = t.get("call", {})
            longrepr = call.get("longrepr", "")

        detail_html = (
            f'<pre style="background:#fff8f8;padding:8px;font-size:0.78em;'
            f'border-left:3px solid #e53935;overflow-x:auto;">'
            f'{_html_escape(str(longrepr)[:1500])}</pre>'
            if longrepr else ""
        )

        test_rows_html += f"""
        <tr style="background:{bg};">
          <td style="padding:6px 12px;font-family:monospace;font-size:0.85em;">{_html_escape(short_id)}</td>
          <td style="padding:6px 12px;">{label}</td>
          <td style="padding:6px 12px;text-align:right;">{duration:.2f}s</td>
        </tr>
        {"<tr><td colspan='3'>" + detail_html + "</td></tr>" if detail_html else ""}
        """

    error_banner = ""
    if report.get("_error_message"):
        error_banner = f"""
        <div style="background:#fff3e0;border-left:4px solid #f57c00;padding:12px 16px;
                    border-radius:4px;margin-bottom:16px;">
          <strong>Runner Error:</strong> {_html_escape(report['_error_message'])}
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:760px;margin:auto;padding:24px;">

  <h2 style="margin-bottom:4px;">🧪 FI GenAI PoC Platform — Test Report</h2>
  <hr style="border:none;border-top:1px solid #ddd;margin-bottom:20px;">

  {error_banner}

  <!-- Status banner -->
  <div style="background:{status_bg};border-left:4px solid {status_color};
              padding:14px 18px;border-radius:4px;margin-bottom:20px;">
    <strong style="font-size:1.15em;color:{status_color};">{status_icon} {status_label}</strong><br>
    <span style="color:#555;">
      {passed} passed &nbsp;·&nbsp; {failed} failed &nbsp;·&nbsp;
      {errors} errors &nbsp;·&nbsp; {skipped} skipped &nbsp;·&nbsp;
      {total} total &nbsp;·&nbsp; {duration_secs:.1f}s
    </span>
  </div>

  <!-- Summary metrics -->
  <table style="border-collapse:collapse;width:100%;margin-bottom:24px;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">✅ Passed</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">❌ Failed</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">⚠️ Errors</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">⏭ Skipped</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">Total</th>
        <th style="padding:8px 12px;text-align:center;border-bottom:2px solid #ddd;">Duration</th>
      </tr>
    </thead>
    <tbody>
      <tr style="text-align:center;font-size:1.1em;font-weight:bold;">
        <td style="padding:10px;color:#2e7d32;">{passed}</td>
        <td style="padding:10px;color:#c62828;">{failed}</td>
        <td style="padding:10px;color:#e65100;">{errors}</td>
        <td style="padding:10px;color:#555;">{skipped}</td>
        <td style="padding:10px;">{total}</td>
        <td style="padding:10px;">{duration_secs:.1f}s</td>
      </tr>
    </tbody>
  </table>

  <!-- Per-test results -->
  <h3 style="margin-bottom:8px;">Test Results</h3>
  <table style="border-collapse:collapse;width:100%;margin-bottom:24px;font-size:0.9em;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">Test</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">Result</th>
        <th style="padding:8px 12px;text-align:right;border-bottom:2px solid #ddd;">Duration</th>
      </tr>
    </thead>
    <tbody>
      {test_rows_html if test_rows_html else '<tr><td colspan="3" style="padding:12px;color:#888;">No test results captured.</td></tr>'}
    </tbody>
  </table>

  <!-- App links -->
  <h3 style="margin-bottom:8px;">Platform Links</h3>
  <table style="border-collapse:collapse;width:100%;margin-bottom:24px;font-size:0.9em;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">App</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">URL</th>
      </tr>
    </thead>
    <tbody>{app_rows_html}</tbody>
  </table>

  <p style="color:#888;font-size:0.85em;">Run at: {timestamp}</p>
  <p style="color:#aaa;font-size:0.8em;">
    Automated test report from the FI GenAI PoC Platform CI/CD pipeline.<br>
    Repo: <a href="https://github.com/cryptominer17/genai-demo">cryptominer17/genai-demo</a>
  </p>
</body>
</html>"""


def _html_escape(text: str) -> str:
    """Minimal HTML escaping for embedding in report."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ===========================================================================
# Step 3 — Send email
# ===========================================================================

def send_report_email(html_body: str, all_ok: bool) -> None:
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("[run_tests] SMTP credentials not set — email not sent.")
        return

    status_word = "PASSED" if all_ok else "FAILED"
    subject = f"[{status_word}] FI GenAI PoC Platform — Test Suite Report"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USERNAME
    msg["To"]      = EMAIL_RECIPIENT

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, EMAIL_RECIPIENT, msg.as_string())
        print(f"[run_tests] Report emailed to {EMAIL_RECIPIENT} — status: {status_word}")
    except smtplib.SMTPAuthenticationError:
        print("[run_tests] SMTP auth failed — check SMTP_USERNAME and SMTP_PASSWORD.")
    except smtplib.SMTPException as exc:
        print(f"[run_tests] SMTP error: {exc}")
    except OSError as exc:
        print(f"[run_tests] Network error reaching SMTP server: {exc}")


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    start = datetime.now(timezone.utc)

    # --- Run tests ---
    report = run_pytest()

    end = datetime.now(timezone.utc)
    duration = (end - start).total_seconds()

    # --- Summarise ---
    summary  = report.get("summary", {})
    failed   = summary.get("failed", 0)
    errors   = summary.get("error", 0)
    passed   = summary.get("passed", 0)
    skipped  = summary.get("skipped", 0)
    all_ok   = (failed == 0 and errors == 0)

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed | {failed} failed | {errors} errors | {skipped} skipped")
    print(f"Duration: {duration:.1f}s")
    print(f"Overall: {'✅ ALL PASSED' if all_ok else '❌ FAILURES DETECTED'}")
    print(f"{'='*60}\n")

    # --- Build and send email ---
    html = build_html_report(report, duration)
    send_report_email(html, all_ok)

    # --- Exit code mirrors pytest's ---
    return report.get("_exit_code", 1 if not all_ok else 0)


if __name__ == "__main__":
    sys.exit(main())
