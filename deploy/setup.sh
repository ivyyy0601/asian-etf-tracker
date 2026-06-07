#!/usr/bin/env bash
#
# One-shot server bootstrap for a fresh Hetzner (Ubuntu 22.04/24.04) VPS.
# Run as root:  sudo bash deploy/setup.sh
#
# It will:
#   1. install system packages (python, venv, git)
#   2. create a dedicated 'etf' user and /opt/etf-tracker
#   3. copy this project into place + create a virtualenv + install deps
#   4. install & start the systemd dashboard service and collection timer
#   5. run the FIRST full data collection (takes 20-40 min)
#
set -euo pipefail

APP_USER="etf"
APP_DIR="/opt/etf-tracker"
# Directory this script lives in (project root = its parent)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> [1/5] Installing system packages + setting timezone to Hong Kong..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git rsync
# Set server clock to HKT so the 08:00 collection timer + last-trading-day logic
# both operate in Hong Kong time.
timedatectl set-timezone Asia/Hong_Kong

echo "==> [2/5] Creating user '$APP_USER' and $APP_DIR ..."
id -u "$APP_USER" &>/dev/null || useradd --system --create-home --shell /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"

echo "==> [3/5] Copying project + building virtualenv ..."
# Copy everything except local data dirs / venv / git.
# NOTE: 'data*/' (trailing slash) matches only directories, so it excludes
# data/, data_ashare/, ... but NOT data_collection.py.
rsync -a --exclude 'venv' --exclude '.venv' --exclude 'data*/' --exclude '.git' \
      "$SRC_DIR/" "$APP_DIR/"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> [4/5] Installing systemd units ..."
cp "$APP_DIR/deploy/etf-dashboard.service" /etc/systemd/system/
cp "$APP_DIR/deploy/etf-collector.service" /etc/systemd/system/
cp "$APP_DIR/deploy/etf-collector.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now etf-dashboard
systemctl enable --now etf-collector.timer

echo "==> [5/5] Kicking off first full data collection in the background..."
echo "    (runs under systemd; watch with: journalctl -u etf-collector -f)"
systemctl start etf-collector

IP="$(hostname -I | awk '{print $1}')"
echo
echo "============================================================"
echo " Done. Dashboard:  http://$IP:8501"
echo " Dashboard logs:   journalctl -u etf-dashboard -f"
echo " Collector logs:   journalctl -u etf-collector -f"
echo " Next runs:        systemctl list-timers etf-collector.timer"
echo "============================================================"
