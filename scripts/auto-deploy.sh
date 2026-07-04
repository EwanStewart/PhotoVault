#!/bin/bash
# Fetch from origin and restart photovault services only if there's something new.
# Driven by photovault-deploy.timer; safe to call manually.

set -euo pipefail

REPO=/home/ewastewa/photovault
BRANCH=master

cd "$REPO"

if ! git diff-index --quiet HEAD --; then
    echo "Working tree has uncommitted changes in $REPO; refusing to deploy" >&2
    exit 1
fi

git fetch --quiet origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

echo "Updating photovault: ${LOCAL:0:7} -> ${REMOTE:0:7}"
git reset --hard "origin/$BRANCH"
venv/bin/pip install --quiet --upgrade -r requirements.txt
sudo -n cp systemd/*.service /etc/systemd/system/
sudo -n /bin/systemctl daemon-reload
sudo -n /bin/systemctl enable --quiet photovault-sync.service
sudo -n /bin/systemctl restart photovault-kiosk.service photovault-brightness.service photovault-sync.service
echo "Restarted photovault at $(git rev-parse --short HEAD)"
