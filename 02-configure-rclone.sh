#!/bin/bash
set -e

echo "=== Google Drive Configuration ==="
echo ""
echo "Follow the prompts to connect Google Drive."
echo "When asked for a name, enter: gdrive"
echo "When asked for storage type, choose: Google Drive"
echo ""
echo "Press Enter to continue..."
read

rclone config

echo ""
echo "=== Done! ==="
echo "Now run 03-setup-project.sh"
