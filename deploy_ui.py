"""
GHCR Deploy UI
==============
A Streamlit app to pull and run Docker images from GHCR
on a remote Digital Ocean droplet (via SSH) or locally.

Usage:
  streamlit run deploy_ui.py
"""

import streamlit as st
import paramiko
import subprocess
import threading
import queue
import os
import json
from pathlib import Path

# ──────────────────────────────────────────────
# Config persistence (saved to ~/.ghcr_deploy.json)
# ──────────────────────────────────────────────
CONFIG_FILE = Path.home() / ".ghcr_deploy.json"

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}

def save_config(data: dict):
    try:
        existing = load_config()
        existing.update(data)
        CONFIG_FILE.write_text(json.dumps(existing, indent=2))
    except Exception:
        pass


# ──────────────────────────────────────────────
# Core deploy functions
# ──────────────────────────────────────────────

def build_docker_commands(image: str, container_name: str, ghcr_user: str, ghcr_token: str) -> list[str]:
    """Returns a list of shell commands to login, pull, stop old container, and run."""
    cmds = []
    if ghcr_token:
        cmds.append(f"echo '{ghcr_token}' | docker login ghcr.io -u {ghcr_user} --password-stdin")
    if container_name:
        # Stop + remove existing container with same name (ignore errors)
        cmds.append(f"docker stop {container_name} 2>/dev/null || true")
        cmds.append(f"docker rm {container_name} 2>/dev/null || true")
    cmds.append(f"docker pull {image}")
    run_cmd = "docker run -d"
    if container_name:
        run_cmd += f" --name {container_name}"
    run_cmd += f" {image}"
    cmds.append(run_cmd)
    return cmds


def run_remote(host: str, user: str, key_path: str, commands: list[str], log_q: queue.Queue):
    """SSH into host, run commands sequentially, push output to log_q."""
    try:
        key = paramiko.RSAKey.from_private_key_file(key_path)
    except Exception:
        try:
            key = paramiko.Ed25519Key.from_private_key_file(key_path)
        except Exception as e:
            log_q.put(f"❌ Could not load SSH key: {e}")
            log_q.put(None)
            return

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        log_q.put(f"🔌 Connecting to {user}@{host}…")
        client.connect(hostname=host, username=user, pkey=key, timeout=15)
        log_q.put("✅ Connected\n")

        for cmd in commands:
            # Mask token in logs
            display_cmd = cmd if "password-stdin" not in cmd else "echo '***' | docker login ghcr.io … (token masked)"
            log_q.put(f"$ {display_cmd}")
            stdin_, stdout_, stderr_ = client.exec_command(cmd, get_pty=True)
            for line in iter(stdout_.readline, ""):
                log_q.put(line.rstrip())
            for line in iter(stderr_.readline, ""):
                log_q.put(f"  {line.rstrip()}")
            exit_code = stdout_.channel.recv_exit_status()
            if exit_code != 0:
                log_q.put(f"⚠️  Exit code {exit_code}")
                break
            log_q.put("")

        log_q.put("🏁 Done")
    except Exception as e:
        log_q.put(f"❌ SSH error: {e}")
    finally:
        client.close()
        log_q.put(None)  # sentinel


def run_local(commands: list[str], log_q: queue.Queue):
    """Run commands locally via subprocess, push output to log_q."""
    try:
        for cmd in commands:
            display_cmd = cmd if "password-stdin" not in cmd else "echo '***' | docker login ghcr.io … (token masked)"
            log_q.put(f"$ {display_cmd}")
            result = subprocess.run(
                cmd, shell=True, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            for line in result.stdout.splitlines():
                log_q.put(line)
            if result.returncode != 0:
                log_q.put(f"⚠️  Exit code {result.returncode}")
                break
            log_q.put("")
        log_q.put("🏁 Done")
    except Exception as e:
        log_q.put(f"❌ Local error: {e}")
    finally:
        log_q.put(None)  # sentinel


# ──────────────────────────────────────────────
# Streamlit UI
# ──────────────────────────────────────────────

st.set_page_config(page_title="GHCR Deploy", page_icon="🐳", layout="wide")

st.title("🐳 GHCR → Docker Deploy")
st.caption("Pull an image from GitHub Container Registry and run it locally or on a Digital Ocean droplet.")

cfg = load_config()

# ── Tabs: Remote / Local ──
tab_remote, tab_local = st.tabs(["☁️ Remote (Digital Ocean)", "💻 Local"])

# ════════════════════════════════════════════
# REMOTE TAB
# ════════════════════════════════════════════
with tab_remote:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🖥️ Droplet")
        droplet_ip   = st.text_input("Droplet IP / Hostname", value=cfg.get("droplet_ip", ""),   placeholder="192.168.1.100")
        ssh_user     = st.text_input("SSH User",              value=cfg.get("ssh_user", "root"),  placeholder="root")
        ssh_key_path = st.text_input("SSH Private Key Path",  value=cfg.get("ssh_key_path", ""), placeholder="~/.ssh/id_rsa")

    with col2:
        st.subheader("📦 Image")
        ghcr_image_r  = st.text_input("GHCR Image",      value=cfg.get("ghcr_image", ""),  placeholder="ghcr.io/yourorg/myapp:latest", key="img_r")
        container_r   = st.text_input("Container Name",  value=cfg.get("container", ""),   placeholder="myapp  (optional)",           key="ctr_r")

    with st.expander("🔑 GHCR Auth (for private images)"):
        ghcr_user_r  = st.text_input("GitHub Username",    value=cfg.get("ghcr_user", ""),  key="ghu_r")
        ghcr_token_r = st.text_input("GitHub PAT (token)", type="password",                 key="ght_r",
                                     help="Personal Access Token with read:packages scope")

    if st.button("🚀 Deploy to Droplet", type="primary", use_container_width=True):
        if not droplet_ip or not ssh_key_path or not ghcr_image_r:
            st.error("Droplet IP, SSH key path, and GHCR image are required.")
        else:
            # Persist non-sensitive fields
            save_config({
                "droplet_ip": droplet_ip, "ssh_user": ssh_user,
                "ssh_key_path": ssh_key_path, "ghcr_image": ghcr_image_r,
                "container": container_r, "ghcr_user": ghcr_user_r,
            })

            key_path_expanded = os.path.expanduser(ssh_key_path)
            cmds = build_docker_commands(ghcr_image_r, container_r, ghcr_user_r, ghcr_token_r)

            log_area = st.empty()
            log_lines: list[str] = []
            q: queue.Queue = queue.Queue()

            t = threading.Thread(
                target=run_remote,
                args=(droplet_ip, ssh_user, key_path_expanded, cmds, q),
                daemon=True
            )
            t.start()

            while True:
                try:
                    msg = q.get(timeout=0.2)
                    if msg is None:
                        break
                    log_lines.append(msg)
                    log_area.code("\n".join(log_lines), language="bash")
                except queue.Empty:
                    pass

            t.join()


# ════════════════════════════════════════════
# LOCAL TAB
# ════════════════════════════════════════════
with tab_local:
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("📦 Image")
        ghcr_image_l = st.text_input("GHCR Image",     value=cfg.get("ghcr_image", ""), placeholder="ghcr.io/yourorg/myapp:latest", key="img_l")
        container_l  = st.text_input("Container Name", value=cfg.get("container", ""),  placeholder="myapp  (optional)",            key="ctr_l")

    with col4:
        st.subheader("🔑 GHCR Auth (for private images)")
        ghcr_user_l  = st.text_input("GitHub Username",    value=cfg.get("ghcr_user", ""), key="ghu_l")
        ghcr_token_l = st.text_input("GitHub PAT (token)", type="password",                key="ght_l",
                                     help="Personal Access Token with read:packages scope")

    if st.button("🚀 Deploy Locally", type="primary", use_container_width=True):
        if not ghcr_image_l:
            st.error("GHCR image is required.")
        else:
            save_config({"ghcr_image": ghcr_image_l, "container": container_l, "ghcr_user": ghcr_user_l})

            cmds = build_docker_commands(ghcr_image_l, container_l, ghcr_user_l, ghcr_token_l)

            log_area_l = st.empty()
            log_lines_l: list[str] = []
            q_l: queue.Queue = queue.Queue()

            t_l = threading.Thread(
                target=run_local,
                args=(cmds, q_l),
                daemon=True
            )
            t_l.start()

            while True:
                try:
                    msg = q_l.get(timeout=0.2)
                    if msg is None:
                        break
                    log_lines_l.append(msg)
                    log_area_l.code("\n".join(log_lines_l), language="bash")
                except queue.Empty:
                    pass

            t_l.join()


# ── Sidebar: saved config summary ──
with st.sidebar:
    st.header("💾 Saved Config")
    c = load_config()
    if c:
        st.json({k: v for k, v in c.items()})
        if st.button("Clear saved config"):
            CONFIG_FILE.unlink(missing_ok=True)
            st.rerun()
    else:
        st.caption("Nothing saved yet — fills in after first deploy.")

    st.divider()
    st.caption("Config saved to `~/.ghcr_deploy.json` (no tokens stored).")
