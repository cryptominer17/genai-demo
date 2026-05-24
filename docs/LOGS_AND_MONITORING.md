# Logs and Monitoring

Where logs live, how to read them, and how to set up ongoing monitoring for the FI GenAI PoC Platform.

---

## Log Locations Summary

| Log | Path | Written by |
|-----|------|-----------|
| Doc Intelligence stdout | `/var/log/streamlit/doc-intelligence.log` | systemd |
| Doc Intelligence stderr | `/var/log/streamlit/doc-intelligence-error.log` | systemd |
| Data Q&A stdout | `/var/log/streamlit/data-qa.log` | systemd |
| Data Q&A stderr | `/var/log/streamlit/data-qa-error.log` | systemd |
| Report Generator stdout | `/var/log/streamlit/report-generator.log` | systemd |
| Report Generator stderr | `/var/log/streamlit/report-generator-error.log` | systemd |
| Deployment log | `/var/log/streamlit/deploy.log` | deploy.sh |
| Nginx access | `/var/log/nginx/fi-genai-poc-access.log` | nginx |
| Nginx error | `/var/log/nginx/fi-genai-poc-error.log` | nginx |
| systemd journal | `journalctl -u streamlit-*` | kernel |

---

## 1. Application Logs

Streamlit app output goes to `/var/log/streamlit/`. Each app has a stdout log (general info) and a stderr log (errors, exceptions, tracebacks).

**Format:** Plain text, one line per log entry. Streamlit adds timestamps automatically.

**Typical stdout entry:**
```
2024-01-15 14:23:01.123 INFO     Watching for changes in these files: ['/opt/fi-genai-poc-platform/apps/...']
2024-01-15 14:23:01.456 INFO     Starting server...
```

**Typical stderr entry (Python traceback):**
```
Traceback (most recent call last):
  File "/opt/fi-genai-poc-platform/shared/llm_client.py", line 42, in call_claude
    response = client.messages.create(...)
anthropic.AuthenticationError: invalid x-api-key
```

**Useful commands:**

```bash
# Follow a log in real time
tail -f /var/log/streamlit/doc-intelligence.log

# Follow the error log
tail -f /var/log/streamlit/doc-intelligence-error.log

# Tail all error logs at once
tail -f /var/log/streamlit/*-error.log

# Search for a specific error type
grep -i "anthropic\|api error\|exception" /var/log/streamlit/doc-intelligence-error.log

# Count errors per app today
grep -c "Error\|Exception" /var/log/streamlit/doc-intelligence-error.log

# Last 100 lines across all error logs
tail -n 100 /var/log/streamlit/*-error.log
```

---

## 2. System Logs (journald)

systemd captures all service output in the system journal in addition to the log files. The journal is useful for startup/crash diagnosis because it includes service lifecycle events.

```bash
# Last 50 lines for a service
journalctl -u streamlit-doc-intelligence -n 50 --no-pager

# Follow live (Ctrl+C to stop)
journalctl -u streamlit-doc-intelligence -f

# All three services together
journalctl -u "streamlit-*" -f

# Entries from the last hour
journalctl -u streamlit-data-qa --since "1 hour ago"

# Show only errors
journalctl -u streamlit-report-generator -p err

# Since last boot
journalctl -u streamlit-doc-intelligence -b
```

---

## 3. Nginx Logs

**Access log** (`/var/log/nginx/fi-genai-poc-access.log`):
Records every HTTP request. Default combined format:
```
<IP> - - [15/Jan/2024:14:23:01 +0000] "GET /Document_AI/ HTTP/1.1" 200 1234 "-" "Mozilla/5.0 ..."
```

Fields: client IP | timestamp | method+path+protocol | status code | bytes | referrer | user agent

**Error log** (`/var/log/nginx/fi-genai-poc-error.log`):
Records nginx-level errors (proxy failures, config issues, connection refused).
```
2024/01/15 14:23:01 [error] 1234#1234: *5 connect() failed (111: Connection refused)
  while connecting to upstream, client: <IP>, server: _, request: "GET /Document_AI/ HTTP/1.1",
  upstream: "http://127.0.0.1:8501/Document_AI/"
```
This specific error means the Streamlit service on port 8501 is not running.

**Useful commands:**

```bash
# Follow access log
tail -f /var/log/nginx/fi-genai-poc-access.log

# Count requests per route
awk '{print $7}' /var/log/nginx/fi-genai-poc-access.log | cut -d/ -f2 | sort | uniq -c | sort -rn

# Find 502 errors (upstream failures)
grep " 502 " /var/log/nginx/fi-genai-poc-access.log | tail -20

# Watch error log
tail -f /var/log/nginx/fi-genai-poc-error.log
```

---

## 4. Deployment Log

`/var/log/streamlit/deploy.log` is written by the `deploy.sh` script during GitHub Actions deployments.

**Format:**
```
[2024-01-15 14:20:00] === Deployment started (commit: abc1234) ===
[2024-01-15 14:20:05] git pull: Already up to date.
[2024-01-15 14:20:10] pip install: Successfully installed ...
[2024-01-15 14:20:15] Restarting streamlit-doc-intelligence...
[2024-01-15 14:20:16] Restarting streamlit-data-qa...
[2024-01-15 14:20:17] Restarting streamlit-report-generator...
[2024-01-15 14:20:30] Health check: PASSED
[2024-01-15 14:20:30] === Deployment complete ===
```

```bash
# View recent deployments
tail -n 50 /var/log/streamlit/deploy.log

# Find failed deployments
grep -i "fail\|error" /var/log/streamlit/deploy.log
```

---

## 5. Useful Commands Reference

| Task | Command |
|------|---------|
| Follow all app error logs | `tail -f /var/log/streamlit/*-error.log` |
| Live journal for all services | `journalctl -u "streamlit-*" -f` |
| Search errors across all logs | `grep -ri "exception\|traceback\|error" /var/log/streamlit/` |
| Count today's nginx requests | `grep "$(date +%d/%b/%Y)" /var/log/nginx/fi-genai-poc-access.log \| wc -l` |
| Check disk usage of logs | `du -sh /var/log/streamlit/ /var/log/nginx/` |
| Watch a metric (refresh every 5s) | `watch -n 5 'tail -n 5 /var/log/streamlit/doc-intelligence-error.log'` |
| Show service restarts | `journalctl -u streamlit-doc-intelligence \| grep "Started\|Stopping"` |

---

## 6. Log Rotation

Without log rotation, `/var/log/streamlit/` will grow indefinitely. Set up logrotate:

```bash
sudo nano /etc/logrotate.d/streamlit
```

Paste:

```
/var/log/streamlit/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 streamlit streamlit
    sharedscripts
    postrotate
        # Signal Streamlit apps to reopen log files
        systemctl kill --signal=USR1 streamlit-doc-intelligence 2>/dev/null || true
        systemctl kill --signal=USR1 streamlit-data-qa 2>/dev/null || true
        systemctl kill --signal=USR1 streamlit-report-generator 2>/dev/null || true
    endscript
}
```

Test the config:
```bash
sudo logrotate --debug /etc/logrotate.d/streamlit
```

This keeps 14 days of compressed logs and rotates daily. Adjust `rotate 14` for more/less retention.

---

## 7. Health Check Monitoring

**Manual run:**
```bash
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh

# JSON output (for integrations)
bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh --json
```

**Automated via cron:**

Set up a cron job to run the health check every 5 minutes and log results:

```bash
sudo crontab -e -u streamlit
```

Add:
```cron
# Run health check every 5 minutes, append to log
*/5 * * * * bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh \
    >> /var/log/streamlit/health-check.log 2>&1
```

**Alerting on failure:**

To get emailed when health check fails, extend the cron entry:

```cron
*/5 * * * * bash /opt/fi-genai-poc-platform/deployment/scripts/health_check.sh \
    >> /var/log/streamlit/health-check.log 2>&1 \
    || echo "Health check failed at $(date)" | mail -s "FI GenAI Platform Alert" you@example.com
```

Requires `mailutils` installed: `sudo apt install mailutils`

**Digital Ocean Droplet Monitoring:**

Enable the DO Monitoring Agent for basic CPU/memory/disk metrics and uptime alerting:
```bash
curl -sSL https://repos.insights.digitalocean.com/install.sh | sudo bash
```

Configure alerts at: Digital Ocean Console → Monitoring → Alerts.

Recommended alerts:
- CPU > 85% for 5 minutes
- Memory > 90%
- Disk > 80%
- Droplet down (built-in ping check)
