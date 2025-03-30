#!/bin/bash

echo "Starting installation script..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Installing Python3..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip
fi

# Install requirements
echo "Installing requirements..."
pip3 install -r requirements.txt

# Check if opencv dependencies are needed
if [ "$(uname)" = "Linux" ]; then
    echo "Installing OpenCV system dependencies..."
    sudo apt-get update
    sudo apt-get install -y libsm6 libxext6 libxrender-dev libgl1-mesa-glx
fi

echo "Installation complete!"