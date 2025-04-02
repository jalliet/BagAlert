<div align="center">
<h3 align="center">BagAlert</h3>

  <p align="center">
    AI-powered surveillance system using object detection to monitor belongings and detect disturbances.
  </p>
</div>

## Table of Contents

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#key-features">Key Features</a></li>
      </ul>
    </li>
    <li><a href="#built-with">Built With</a></li>
    <li><a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#more-info">More Information</a></li>
  </ol>
</details>

## About The Project

BagAlert is an AI-powered security system designed to monitor your belongings and detect disturbances. It utilizes object detection via a camera and the aitrios-rpi-application-module-library to identify and track items. If an object is moved or goes missing, the system triggers an alert. The system also has an RFID trigger to arm the system.

### Key Features

- **Object Detection:** Uses the IMX500 and SSDMobileNetV2FPNLite320x320 model to identify objects in the camera's view.
- **Disturbance Detection:** Calculates Intersection over Union (IoU) to determine if protected objects have been moved.
- **Real-time Alerts:** Sends alerts via WebSocket to a web-based frontend when disturbances are detected.
- **Web Interface:** Provides a user interface to view the camera feed, activate/deactivate protection, and view recent alerts.
- **RFID Trigger:** Simulates an RFID trigger to activate protection (can be integrated with actual RFID hardware).

## Built With

- **Backend:**
  - Python 3
  - Flask
  - FastAPI
  - OpenCV
  - modlib (aitrios-rpi-application-module-library)
  - uvicorn
- **Frontend:**
  - React
  - Material UI
  - Socket.IO Client
- **Hardware (intended):**
  - Raspberry Pi
  - IMX500 Camera
  - ESP32 (for RFID)

## Getting Started

To get started with BagAlert, follow the instructions below.

### Prerequisites

- Raspberry Pi with a camera (IMX500 recommended)
- Python 3.6+
- Node.js and npm (for the frontend)
- Access to a mobile hotspot/internet connection for the Raspberry Pi and your development machine to communicate

### Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/jalliet/bagalert.git
   cd bagalert
   ```

2. **Backend Setup:**
   - Run the `backend_setup.sh` script:
     ```sh
     ./backend_setup.sh
     ```
     This script performs the following actions:
       - Installs ModLib and its dependencies.
       - Creates and activates a Python virtual environment.
       - Installs required Python packages using `install_requirements.sh`.
       - Starts the camera server (`camera/camera_server.py`).

3.  **Install ModLib:**
    ```sh
    ./install_modlib.sh
    ```
    This script handles the installation of the aitrios-rpi-application-module-library and its dependencies.

4. **Frontend Setup:**
   - Navigate to the `frontend` directory:
     ```sh
     cd frontend
     ```
   - Install npm packages:
     ```sh
     npm install --force
     ```
   - Start the frontend:
     ```sh
     npm run start
     ```
   - The frontend will be accessible at `http://localhost:3000`.

5. **ESP32 Setup (RFID - Optional):**
   - Open the `rfid/rfid.ino` file in the Arduino IDE.
   - Modify the `ssid`, `password`, and `mqtt_server` variables with your network and Raspberry Pi's IP address.
   - Upload the code to your ESP32.

6. **MQTT Broker Setup (If using MQTT):**
   - Ensure an MQTT broker is running and accessible to both the Raspberry Pi and the ESP32.
   - Modify the `mqtt_publisher.py` and `mqtt_suscriber.py` files with the correct broker IP address.

## Running on Raspberry Pi

Follow these steps to run BagAlert on your Raspberry Pi:

1. **Navigate to Project Directory:**
   ```bash
   cd bagalert
   ```

2. **Setup Instructions:**

   ### First Time Setup
   If you haven't installed the requirements yet:
   ```bash
   # Make scripts executable
   chmod +x backend_setup.sh frontend_setup.sh install_requirements.sh
   
   # Install dependencies and set up the environment
   ./install_requirements.sh
   ```

   ### For All Runs (Including First Time)
   ```bash
   # Make scripts executable (if not done already)
   chmod +x backend_setup.sh frontend_setup.sh
   ```

3. **Start Backend Server:**
   ```bash
   # In your first terminal window
   ./backend_setup.sh
   ```

4. **Launch Frontend Server:**
   ```bash
   # Open a new terminal window
   cd bagalert
   ./frontend_setup.sh
   ```

5. **Start MQTT Subscriber:**
   ```bash
   # Open a new terminal window
   cd bagalert/mqtt
   python mqtt_subscriber.py
   ```

The system should now be up and running! You can access the web interface at `http://localhost:3000` and start monitoring your belongings.

### System Architecture

BagAlert uses a modular architecture with three main components:

1. **Main Application (`main.py`):**
   - System initialization and coordination
   - Service management
   - Event handling
   - Graceful shutdown procedures

2. **Camera Service (`camera_service.py`):**
   - Camera feed management
   - Object detection and tracking
   - Protection state management
   - Web interface and WebSocket streaming
   - Alert generation

3. **RFID Service (`rfid_service.py`):**
   - MQTT client management
   - RFID event processing
   - User session handling
   - Service communication

### Key Features

- **Inter-service Communication:** Event-driven architecture ensuring smooth communication between components
- **Configuration Management:** Flexible configuration through external files and environment variables
- **Logging and Monitoring:** Comprehensive activity tracking and status reporting
- **Web Interface:** Real-time status display, live camera feed, and alert notifications

## More info

- [DevPost](https://devpost.com/software/bagalert)
- [Hackster.io](https://www.hackster.io/bagalert/bagalert-f29fa2)
