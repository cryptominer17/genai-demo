"""
notify.py — Sends HTML deployment status emails via Gmail SMTP (TLS port 587).

Usage (CLI):
    python3 deployment/email/notify.py "SUCCESS" "All 3 services running"
    python3 deployment/email/notify.py "FAILURE" "Deploy failed at line 42"

Environment variables (loaded from .env if present):
    SMTP_SERVER       — default: smtp.gmail.com
    SMTP_PORT         — default: 587
    SMTP_USERNAME     — Gmail sender address
    SMTP_PASSWORD     — Gmail App Password
    EMAIL_RECIPIENT   — destination address
"""

import smtplib
import sys
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on environment variables directly


# ── Config ────────────────────────────────────────────────────────────────────
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "shouvik.pradhan@gmail.com")

DROPLET_IP = os.environ.get("DROPLET_IP", "<DROPLET_IP>")

APP_URLS = {
    "Document AI":  f"http://{DROPLET_IP}/Document_AI",
    "Text to SQL":  f"http://{DROPLET_IP}/Text_to_SQL",
    "BI Dashboard": f"http://{DROPLET_IP}/BI_Dashboard",
}


# ── Email builder ─────────────────────────────────────────────────────────────
def _build_html(status: str, message: str) -> str:
    is_success = status.upper() == "SUCCESS"
    status_color = "#2e7d32" if is_success else "#c62828"
    status_bg    = "#e8f5e9" if is_success else "#ffebee"
    status_icon  = "✅" if is_success else "❌"
    timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    app_rows = "\n".join(
        f'<tr><td style="padding:6px 12px;">{name}</td>'
        f'<td style="padding:6px 12px;"><a href="{url}">{url}</a></td></tr>'
        for name, url in APP_URLS.items()
    )

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:640px;margin:auto;padding:24px;">
  <h2 style="margin-bottom:4px;">FI GenAI PoC Platform — Deployment Notification</h2>
  <hr style="border:none;border-top:1px solid #ddd;margin-bottom:20px;">

  <div style="background:{status_bg};border-left:4px solid {status_color};
              padding:14px 18px;border-radius:4px;margin-bottom:20px;">
    <strong style="font-size:1.1em;color:{status_color};">{status_icon} Status: {status.upper()}</strong><br>
    <span style="color:#555;">{message}</span>
  </div>

  <table style="border-collapse:collapse;width:100%;margin-bottom:20px;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">App</th>
        <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #ddd;">URL</th>
      </tr>
    </thead>
    <tbody>
      {app_rows}
    </tbody>
  </table>

  <p style="color:#888;font-size:0.85em;">Deployed at: {timestamp}</p>
  <p style="color:#aaa;font-size:0.8em;">
    This is an automated notification from the GitHub Actions CI/CD pipeline.<br>
    Repo: <a href="https://github.com/cryptominer17/genai-demo">cryptominer17/genai-demo</a>
  </p>
</body>
</html>
"""


# ── Core function ─────────────────────────────────────────────────────────────
def send_deployment_notification(status: str, message: str) -> None:
    """
    Send an HTML deployment notification email.

    Args:
        status:  "SUCCESS" or "FAILURE"
        message: Short description of what happened
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("[notify.py] ERROR: SMTP_USERNAME or SMTP_PASSWORD not set. Email not sent.")
        return

    subject = f"[{status.upper()}] FI GenAI PoC Platform — Deployment {'Succeeded' if status.upper() == 'SUCCESS' else 'Failed'}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USERNAME
    msg["To"]      = EMAIL_RECIPIENT

    html_body = _build_html(status, message)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, EMAIL_RECIPIENT, msg.as_string())
        print(f"[notify.py] Email sent to {EMAIL_RECIPIENT} — status: {status.upper()}")
    except smtplib.SMTPAuthenticationError:
        print("[notify.py] ERROR: SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD (use a Gmail App Password).")
    except smtplib.SMTPException as exc:
        print(f"[notify.py] ERROR: SMTP error — {exc}")
    except OSError as exc:
        print(f"[notify.py] ERROR: Network error reaching SMTP server — {exc}")


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 notify.py <STATUS> <MESSAGE>")
        print("  STATUS:  SUCCESS or FAILURE")
        print("  MESSAGE: Short description")
        sys.exit(1)

    cli_status  = sys.argv[1]
    cli_message = sys.argv[2]
    send_deployment_notification(cli_status, cli_message)
