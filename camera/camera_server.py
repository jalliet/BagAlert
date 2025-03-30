import cv2
import time
import numpy as np
import base64
import asyncio
from typing import List
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from modlib.apps import Annotator
from modlib.devices import AiCamera
from modlib.models.zoo import SSDMobileNetV2FPNLite320x320

# Global variables
camera_task = None
frame_rate = 30
last_frame = None

device = AiCamera()
model = SSDMobileNetV2FPNLite320x320()

# Camera async context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize camera and start frame processing
    global camera_task
    camera_task = asyncio.create_task(process_camera_frames())
    print("Camera processing started")
    
    yield  # Here the FastAPI application runs
    
    # Shutdown: cancel the camera task
    if camera_task:
        camera_task.cancel()
        try:
            await camera_task
        except asyncio.CancelledError:
            print("Camera task cancelled")

# Create FastAPI app with the lifespan context manager
app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Client disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
                disconnected_clients.append(connection)
        
        # Clean up any disconnected clients
        for client in disconnected_clients:
            if client in self.active_connections:
                self.active_connections.remove(client)

manager = ConnectionManager()

# Main camera processing function
async def process_camera_frames():
    global last_frame, frame_rate
    
    try:
        print("Initializing AI Camera...")
        
        
        try:
            print("Deploying model...")
            device.deploy(model)
            print("Model deployed successfully")
        except RuntimeError as e:
            print(f"Warning: Failed to deploy model: {e}")
            print("Continuing without redeploying the model...")
        
        annotator = Annotator(thickness=1, text_thickness=1, text_scale=0.4)
        
        print("Starting camera stream...")
        with device as stream:
            for frame in stream:
                # print("here 2")
                try:
                    # Process current frame
                    start_time = time.time()
                    
                    # Run object detection
                    detections = frame.detections[frame.detections.confidence > 0.55]
                    labels = [f"{model.labels[class_id]}: {score:0.2f}" 
                             for _, score, class_id, _ in detections]
                    
                    # Annotate the frame
                    annotator.annotate_boxes(frame, detections, labels=labels)
                    
                    # Convert frame to cv2 image
                    if hasattr(frame, 'image'):
                        pil_img = frame.image
                        cv2_img = np.array(pil_img)
                        if cv2_img.shape[2] == 3:
                            cv2_img = cv2_img[:, :, ::-1].copy()
                    elif hasattr(frame, 'array'):
                        cv2_img = frame.array.copy()
                    else:
                        cv2_img = np.array(frame)
                    
                    # Encode to base64
                    _, buffer = cv2.imencode('.jpg', cv2_img)
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Update the last frame
                    last_frame = img_base64
                    
                    # Broadcast the frame if we have active connections
                    if manager.active_connections:
                        await manager.broadcast(img_base64)
                    
                    # Calculate processing time and sleep to maintain frame rate
                    process_time = time.time() - start_time
                    sleep_time = max(0, (1.0 / frame_rate) - process_time)
                    
                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    
                except asyncio.CancelledError:
                    print("Camera processing cancelled")
                    break
                except Exception as e:
                    print(f"Error processing frame: {e}")
                    await asyncio.sleep(0.1)  # Brief pause on error
                
                # Allow other tasks to run
                await asyncio.sleep(0)
    
    except Exception as e:
        print(f"Camera error: {e}")
    finally:
        print("Camera stream ended")

# HTML page for testing
@app.get("/", response_class=HTMLResponse)
async def get():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Camera WebSocket Test</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 20px; }
                img { max-width: 100%; border: 1px solid #ddd; margin: 20px 0; }
                button { padding: 10px 20px; margin: 5px; cursor: pointer; }
                .controls { margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>Camera WebSocket Test</h1>
            <div>
                <img id="cameraFeed" src="" alt="Camera Feed" />
            </div>
            <div class="controls">
                <button onclick="setFrameRate(15)">15 FPS</button>
                <button onclick="setFrameRate(30)">30 FPS</button>
            </div>
            <div id="status">Connecting...</div>
            
            <script>
                let ws;
                let reconnectTimer;
                
                function connectWebSocket() {
                    ws = new WebSocket("ws://" + window.location.host + "/live");
                    
                    ws.onopen = function(event) {
                        clearTimeout(reconnectTimer);
                        document.getElementById("status").textContent = "Connected";
                    };
                    
                    ws.onmessage = function(event) {
                        document.getElementById("cameraFeed").src = "data:image/jpeg;base64," + event.data;
                    };
                    
                    ws.onclose = function(event) {
                        document.getElementById("status").textContent = "Disconnected - Reconnecting...";
                        reconnectTimer = setTimeout(connectWebSocket, 2000);
                    };
                    
                    ws.onerror = function(error) {
                        console.error("WebSocket error:", error);
                    };
                }
                
                function setFrameRate(fps) {
                    fetch("/set_frame_rate/" + fps)
                        .then(response => response.json())
                        .then(data => {
                            console.log("Frame rate set to:", data.frame_rate);
                        })
                        .catch(error => {
                            console.error("Error setting frame rate:", error);
                        });
                }
                
                // Connect when page loads
                connectWebSocket();
            </script>
        </body>
    </html>
    """

# WebSocket endpoint for camera stream
@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Send the current frame immediately if available
    if last_frame:
        await websocket.send_text(last_frame)
    
    try:
        while True:
            # Wait for any commands from client (optional)
            data = await websocket.receive_text()
            print(f"Received from client: {data}")
            
            # Process commands if needed (not implemented here)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# API endpoint to get camera status
@app.get("/status")
async def get_status():
    global camera_task, frame_rate
    return {
        "running": camera_task is not None and not camera_task.done(),
        "frame_rate": frame_rate,
        "active_connections": len(manager.active_connections)
    }

# API endpoint to set frame rate
@app.get("/set_frame_rate/{rate}")
async def set_frame_rate(rate: int):
    global frame_rate
    if 1 <= rate <= 60:
        frame_rate = rate
        return {"success": True, "frame_rate": frame_rate}
    return {"success": False, "message": "Frame rate must be between 1 and 60 FPS"}

if __name__ == "__main__":
    # Get the machine's IP addresses for display
    import socket
    def get_ip_addresses():
        ip_list = []
        try:
            interfaces = socket.getaddrinfo(socket.gethostname(), None)
            for info in interfaces:
                ip = info[4][0]
                if '.' in ip and ip != '127.0.0.1':
                    ip_list.append(ip)
        except Exception as e:
            print(f"Error getting IP addresses: {e}")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('10.255.255.255', 1))
                ip = s.getsockname()[0]
                ip_list.append(ip)
            except Exception:
                ip_list.append('127.0.0.1')
            finally:
                s.close()
        return ip_list
    
    # Print server information
    port = 5000
    print("\n" + "="*80)
    print("⚡ STARTING FASTAPI ASYNC CAMERA SERVER ⚡")
    print("="*80)
    print("\n📱 Access the camera stream from your devices at:")
    
    ip_addresses = get_ip_addresses()
    for ip in ip_addresses:
        print(f"\n    http://{ip}:{port}")
        print(f"    WebSocket: ws://{ip}:{port}/live")
    
    print("\n" + "="*80 + "\n")
    
    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=port)