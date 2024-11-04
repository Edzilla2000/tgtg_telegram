#!/bin/bash

# Replace these with your actual paths
SCRIPT_PATH="program_path"
VENV_PATH="${SCRIPT_PATH}/.venv"
PYTHON_SCRIPT="${SCRIPT_PATH}/TooGoodTooGo.py"
CONF_PATH="${SCRIPT_PATH}/.env"

# Activate virtual environment and run script
cd "${SCRIPT_PATH}"
source "${VENV_PATH}/bin/activate"
source "${CONF_PATH}"
python "${PYTHON_SCRIPT}"
deactivate
