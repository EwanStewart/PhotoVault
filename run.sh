#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

if [ ! -d "${VENV_DIR}" ]; then
    echo "Virtual environment not found. Run ./install_venv.sh first."
    exit 1
fi

# Load environment variables
if [ -f "${SCRIPT_DIR}/.env" ]; then
    export $(grep -v '^#' "${SCRIPT_DIR}/.env" | xargs)
fi

source "${VENV_DIR}/bin/activate"

export PHOTOS_DIR="${SCRIPT_DIR}/photos"

cd "${SCRIPT_DIR}/src"
python -m photovault.main
