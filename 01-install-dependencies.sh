#!/bin/bash
set -e

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

echo ""
echo "=== Installing rclone ==="
sudo apt update && sudo apt install -y rclone

echo ""
echo "=== Done! ==="
echo "Please log out and back in (or reboot), then run 02-configure-rclone.sh"
