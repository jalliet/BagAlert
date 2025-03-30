#!/bin/bash

# Backend setup
./install_modlib.sh
source .venv/bin/activate
cd camera
python camera_server.py
