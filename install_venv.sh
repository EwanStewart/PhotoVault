#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

echo "Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libheif-dev

echo "Creating virtual environment"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

echo "Installing Python packages"
pip install --upgrade pip
pip install -r "${SCRIPT_DIR}/requirements.txt"

echo "Done. Run ./run.sh to start the photo frame."
