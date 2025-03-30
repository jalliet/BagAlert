#!/bin/bash

echo "Installing ModLib..."

sudo apt update && sudo apt full-upgrade
sudo apt install imx500-all
sudo apt install python3-opencv python3-munkres python3-picamera2

python -m venv .venv --system-site-packages
. .venv/bin/activate
pip install modlib-1.0.0-py3-none-any.whl

echo "ModLib installation complete!"

cd ../../BagAlert

echo "Installing BagAlert requirements..."
./install_requirements.sh