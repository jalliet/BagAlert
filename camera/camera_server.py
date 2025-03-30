import cv2
import time
import numpy as np
import base64
import asyncio
import json
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from modlib.apps import Annotator
from modlib.devices import AiCamera
from modlib.models.zoo import SSDMobileNetV2FPNLite320x320

# Configuration
MOVEMENT_THRESHOLD = 0.6  # IoU threshold - below this triggers alert
CHECK_FREQUENCY = 1  # Check every N seconds for disturbances
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence for object detection

# Global variables
camera_task = None
frame_rate = 30
last_frame = None
protected_items = []
protection_active = False
last_disturbance_check_time = 0

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

    async def broadcast_frame(self, frame: str):
        """Send frame to all clients"""
        disconnected_clients = []
        for connection in self.active_connections:
            try:
                await connection.send_text(frame)
            except Exception as e:
                print(f"Error sending frame to client: {e}")
                disconnected_clients.append(connection)
        
        # Clean up disconnected clients
        for client in disconnected_clients:
            if client in self.active_connections:
                self.active_connections.remove(client)
    
    async def broadcast_alert(self, alert_data: Dict[str, Any]):
        """Send alert data to all clients"""
        message = json.dumps({"type": "alert", "data": alert_data})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error sending alert to client: {e}")

manager = ConnectionManager()

# Crop image from bounding box
def crop_image(image, bbox):
    """
    Crop a region from an image based on a bounding box.
    
    Args:
        image: Input image (numpy array from OpenCV)
        bbox: Bounding box in format [x, y, width, height]
        
    Returns:
        Cropped image
    """
    # Extract coordinates
    x, y, width, height = bbox
    
    # Convert to integers (in case they're floats)
    x, y, width, height = int(x), int(y), int(width), int(height)
    
    # Ensure coordinates are within image boundaries
    height_img, width_img = image.shape[:2]
    
    # Constrain to image boundaries
    x = max(0, x)
    y = max(0, y)
    width = min(width, width_img - x)
    height = min(height, height_img - y)
    
    # Perform the crop
    cropped_image = image[y:y+height, x:x+width]
    
    return cropped_image

# Calculate IoU between two bounding boxes
def calculate_iou(box1, box2):
    """
    Calculate Intersection over Union between two bounding boxes.
    
    Args:
        box1: First bounding box in format [x, y, width, height]
        box2: Second bounding box in format [x, y, width, height]
        
    Returns:
        IoU score between 0 and 1
    """
    # Convert [x, y, width, height] to [x1, y1, x2, y2] format
    box1_x1, box1_y1 = box1[0], box1[1]
    box1_x2, box1_y2 = box1[0] + box1[2], box1[1] + box1[3]
    
    box2_x1, box2_y1 = box2[0], box2[1]
    box2_x2, box2_y2 = box2[0] + box2[2], box2[1] + box2[3]
    
    # Calculate area of each box
    box1_area = box1[2] * box1[3]
    box2_area = box2[2] * box2[3]
    
    # Calculate coordinates of intersection
    x1 = max(box1_x1, box2_x1)
    y1 = max(box1_y1, box2_y1)
    x2 = min(box1_x2, box2_x2)
    y2 = min(box1_y2, box2_y2)
    
    # Check if there is an intersection
    if x2 < x1 or y2 < y1:
        return 0.0  # No intersection
    
    # Calculate intersection area
    intersection_area = (x2 - x1) * (y2 - y1)
    
    # Calculate union area (sum of areas minus intersection)
    union_area = box1_area + box2_area - intersection_area
    
    # Avoid division by zero
    if union_area == 0:
        return 0.0
    
    # Calculate IoU
    iou = intersection_area / union_area
    
    return iou

# Find best matching object
def find_best_match(protected_item, current_objects):
    """
    Find the best matching object from current_objects for a protected item.
    
    Args:
        protected_item: Dictionary containing info about a protected item
        current_objects: List of dictionaries of currently detected objects
    
    Returns:
        Best matching object or None if no good match found
    """
    best_match = None
    best_score = 0
    min_score_threshold = 0.3  # Minimum IoU score to be considered a match
    
    # Filter objects of the same class first
    same_class_objects = [obj for obj in current_objects 
                        if obj['class'] == protected_item['class']]
    
    # If we have objects of the same class, find the one with best spatial overlap
    for obj in same_class_objects:
        iou = calculate_iou(protected_item['bbox'], obj['bbox'])
        
        if iou > best_score:
            best_score = iou
            best_match = obj
    
    # If we didn't find a good match with the same class,
    # look for objects of different classes (in case of misclassification)
    if best_score < min_score_threshold:
        for obj in current_objects:
            if obj['class'] != protected_item['class']:
                iou = calculate_iou(protected_item['bbox'], obj['bbox'])
                # Apply a penalty for different class
                adjusted_score = iou * 0.8  # 20% penalty for class mismatch
                
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_match = obj
    
    # If the match is too poor, return None
    if best_score < min_score_threshold:
        return None
        
    return best_match

# Initialize protection by detecting and storing objects
def initialize_protection(cv2_img, detections):
    """When user activates protection, detect and catalog objects"""
    global protected_items
    
    # Clear any existing protected items
    protected_items = []
    
    for detection in detections:
        if detection['confidence'] > CONFIDENCE_THRESHOLD:
            # Store the protection data
            protected_items.append({
                'class': detection['class'],
                'bbox': detection['bbox'],
                'initial_frame': crop_image(cv2_img, detection['bbox']),
                'confidence': detection['confidence'],
                'last_seen': time.time()
            })
    
    print(f"Protection initialized with {len(protected_items)} objects")
    return protected_items

# Check for disturbances in protected objects
def check_for_disturbance(cv2_img, detections):
    """Check if protected objects have moved"""
    if not protected_items:
        return []
    
    disturbances = []
    
    for protected in protected_items:
        best_match = find_best_match(protected, detections)
        
        if best_match:
            # Calculate IoU between original and current position
            iou = calculate_iou(protected['bbox'], best_match['bbox'])
            
            if iou < MOVEMENT_THRESHOLD:
                # Object has moved significantly
                disturbances.append({
                    'item': protected['class'],
                    'original_bbox': protected['bbox'],
                    'current_bbox': best_match['bbox'],
                    'movement_score': 1 - iou,
                    'current_image': base64.b64encode(cv2.imencode('.jpg', 
                                    crop_image(cv2_img, best_match['bbox']))[1]).decode('utf-8')
                })
        else:
            # Object not found at all - definitely disturbed
            disturbances.append({
                'item': protected['class'],
                'original_bbox': protected['bbox'],
                'current_bbox': None,
                'movement_score': 1.0,
                'missing': True
            })
    
    return disturbances

# Process detections from a frame
def process_detections(frame, annotator):
    """
    Process a single frame: run object detection and return detections.
    Also annotate the frame.
    """
    detections = frame.detections[frame.detections.confidence > CONFIDENCE_THRESHOLD]
    detection_results = []
    labels = []
    
    for detection in detections:
        _, score, class_id, bbox = detection
        label = f"{model.labels[class_id]}: {score:0.2f}"
        labels.append(label)
        detection_results.append({
            "class": model.labels[class_id],
            "confidence": score,
            "bbox": bbox
        })
    
    # Annotate the frame
    annotator.annotate_boxes(frame, detections, labels=labels)
    return detection_results

# Main camera processing function
async def process_camera_frames():
    global last_frame, frame_rate, protection_active, last_disturbance_check_time
    
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
                try:
                    # Process current frame
                    start_time = time.time()
                    
                    # Process detections
                    detections = process_detections(frame, annotator)
                    
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
                    
                    # Check for disturbances if protection is active
                    current_time = time.time()
                    if (protection_active and 
                        current_time - last_disturbance_check_time > CHECK_FREQUENCY):
                        
                        disturbances = check_for_disturbance(cv2_img, detections)
                        last_disturbance_check_time = current_time
                        
                        if disturbances:
                            print(f"Detected {len(disturbances)} disturbances")
                            
                            # Add visual indicators for disturbances
                            for disturbance in disturbances:
                                if 'current_bbox' in disturbance and disturbance['current_bbox']:
                                    x, y, w, h = [int(v) for v in disturbance['current_bbox']]
                                    # Draw red rectangle around disturbed object
                                    cv2.rectangle(cv2_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                                    cv2.putText(cv2_img, f"ALERT: {disturbance['item']}", 
                                                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                                                0.5, (0, 0, 255), 2)
                            
                            # Send alert to clients
                            alert_data = {
                                "timestamp": current_time,
                                "disturbances": disturbances
                            }
                            await manager.broadcast_alert(alert_data)
                    
                    # Encode to base64
                    _, buffer = cv2.imencode('.jpg', cv2_img)
                    img_base64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Update the last frame
                    last_frame = img_base64
                    
                    # Broadcast the frame if we have active connections
                    if manager.active_connections:
                        await manager.broadcast_frame(img_base64)
                    
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
            <title>BagAlert Camera</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 20px; background-color: #222; color: white; }
                img { max-width: 100%; border: 1px solid #444; margin: 20px 0; }
                button { padding: 10px 20px; margin: 5px; cursor: pointer; background-color: #333; color: white; border: 1px solid #666; }
                button.active { background-color: #080; }
                button.alert { background-color: #800; }
                .controls { margin: 20px 0; }
                .status { margin: 10px 0; padding: 10px; background-color: #333; border-radius: 4px; }
                #alerts { max-height: 200px; overflow-y: auto; margin-top: 20px; text-align: left; padding: 10px; background-color: #333; border-radius: 4px; }
                .alert-item { margin: 5px 0; padding: 5px; border-left: 3px solid #f00; }
            </style>
        </head>
        <body>
            <h1>BagAlert Camera</h1>
            <div>
                <img id="cameraFeed" src="" alt="Camera Feed" />
            </div>
            <div class="controls">
                <button id="protectBtn" onclick="toggleProtection()">Activate Protection</button>
                <button onclick="setFrameRate(15)">15 FPS</button>
                <button onclick="setFrameRate(30)">30 FPS</button>
            </div>
            <div id="status" class="status">Connecting...</div>
            <div id="alerts">
                <h3>Alerts</h3>
                <div id="alertsList"></div>
            </div>
            
            <script>
                let ws;
                let reconnectTimer;
                let protectionActive = false;
                
                function connectWebSocket() {
                    ws = new WebSocket("ws://" + window.location.host + "/live");
                    
                    ws.onopen = function(event) {
                        clearTimeout(reconnectTimer);
                        document.getElementById("status").textContent = "Connected to camera server";
                    };
                    
                    ws.onmessage = function(event) {
                        // Check if the message is an alert or a frame
                        try {
                            const jsonMsg = JSON.parse(event.data);
                            if (jsonMsg.type === "alert") {
                                // Handle alert
                                displayAlert(jsonMsg.data);
                            }
                        } catch (e) {
                            // Not JSON, so it's a frame
                            document.getElementById("cameraFeed").src = "data:image/jpeg;base64," + event.data;
                        }
                    };
                    
                    ws.onclose = function(event) {
                        document.getElementById("status").textContent = "Disconnected - Reconnecting...";
                        reconnectTimer = setTimeout(connectWebSocket, 2000);
                    };
                    
                    ws.onerror = function(error) {
                        console.error("WebSocket error:", error);
                    };
                }
                
                function displayAlert(alertData) {
                    const alertsList = document.getElementById("alertsList");
                    const timestamp = new Date(alertData.timestamp * 1000).toLocaleTimeString();
                    
                    alertData.disturbances.forEach(disturbance => {
                        const alertItem = document.createElement("div");
                        alertItem.className = "alert-item";
                        
                        if (disturbance.missing) {
                            alertItem.innerHTML = `<strong>${timestamp}</strong>: ${disturbance.item} is MISSING`;
                        } else {
                            alertItem.innerHTML = `<strong>${timestamp}</strong>: ${disturbance.item} has moved (${Math.round(disturbance.movement_score * 100)}% change)`;
                        }
                        
                        alertsList.insertBefore(alertItem, alertsList.firstChild);
                    });
                }
                
                function toggleProtection() {
                    protectionActive = !protectionActive;
                    const btn = document.getElementById("protectBtn");
                    
                    if (protectionActive) {
                        btn.textContent = "Deactivate Protection";
                        btn.classList.add("active");
                        fetch("/activate_protection")
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById("status").textContent = 
                                    `Protection active: monitoring ${data.object_count} objects`;
                            });
                    } else {
                        btn.textContent = "Activate Protection";
                        btn.classList.remove("active");
                        fetch("/deactivate_protection")
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById("status").textContent = "Protection deactivated";
                            });
                    }
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
            
            # Process commands if needed
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# API endpoint to get camera status
@app.get("/status")
async def get_status():
    global camera_task, frame_rate, protection_active
    return {
        "running": camera_task is not None and not camera_task.done(),
        "frame_rate": frame_rate,
        "active_connections": len(manager.active_connections),
        "protection_active": protection_active,
        "protected_items_count": len(protected_items)
    }

# API endpoint to set frame rate
@app.get("/set_frame_rate/{rate}")
async def set_frame_rate(rate: int):
    global frame_rate
    if 1 <= rate <= 60:
        frame_rate = rate
        return {"success": True, "frame_rate": frame_rate}
    return {"success": False, "message": "Frame rate must be between 1 and 60 FPS"}

# API endpoint to activate protection
@app.get("/activate_protection")
async def activate_protection():
    global protection_active, last_frame
    
    # We need last_frame and a way to process its detections
    if last_frame:
        # Decode the base64 image
        img_bytes = base64.b64decode(last_frame)
        nparr = np.frombuffer(img_bytes, np.uint8)
        cv2_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Get detections on the current frame
        with device as stream:
            # Get a single frame
            frame = next(stream)
            detections = process_detections(frame, Annotator())
            
            # Initialize protection
            initialize_protection(cv2_img, detections)
        
        protection_active = True
        return {"success": True, "object_count": len(protected_items)}
    
    return {"success": False, "message": "No frame available to initialize protection"}

# API endpoint to deactivate protection
@app.get("/deactivate_protection")
async def deactivate_protection():
    global protection_active, protected_items
    protection_active = False
    protected_items = []
    return {"success": True}

# API endpoint to simulate RFID trigger (for testing without actual RFID hardware)
@app.get("/simulate_rfid_trigger")
async def simulate_rfid_trigger():
    await activate_protection()
    return {"message": "RFID trigger simulated, protection activated"}

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
    print("⚡ STARTING BAGALERT CAMERA SERVER ⚡")
    print("="*80)
    print("\n📱 Access the camera stream from your devices at:")
    
    ip_addresses = get_ip_addresses()
    for ip in ip_addresses:
        print(f"\n    http://{ip}:{port}")
        print(f"    WebSocket: ws://{ip}:{port}/live")
    
    print("\n" + "="*80 + "\n")
    
    # Run the FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=port)