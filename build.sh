#!/bin/bash

# --- Stop on any error ---
set -e

VERSION="1.0"

echo -e "\nCreating virtual environment...\n"
# Create a new, clean virtual environment using Python 3.13
python3.13 -m venv venv

# Activate it
source venv/bin/activate

echo -e "\nInstalling dependencies (if necessary)...\n"
# This installs your app's needs (PySide6, requests)
# and the build tool (pyinstaller) all at once.
pip install PySide6 requests pyinstaller

echo -e "\nBuilding...\n"
pyinstaller \
    --onefile \
    --noconsole \
    --name "ProjectPlus-REX-Updater-$VERSION" \
    --add-binary="/usr/bin/7z:./usr/bin" \
    --distpath="~/Applications" \
    --workpath="/tmp" \
    main.py

rm *.spec
