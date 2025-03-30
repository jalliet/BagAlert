import cv2
import time
import numpy as np
import base64
import asyncio
import json
from typing import List, Dict, Any
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
from modlib.apps import Annotator
from modlib.devices import AiCamera
from modlib.models.zoo import SSDMobileNetV2FPNLite320x320

# Configuration
MOVEMENT_THRESHOLD = 0.6
CHECK_FREQUENCY = 1
CONFIDENCE_THRESHOLD = 0.7

# Global variables
camera_task = None
frame_rate = 30
last_frame = None
protected_items = []
protection_active = False
last_disturbance_check_time = 0

device = AiCamera()
model = SSDMobileNetV2FPNLite320x320()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global camera_task
    camera_task = asyncio.create_task(process_camera_frames())
    yield
    if camera_task:
        camera_task.cancel()
        await camera_task

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_frame(self, frame: str):
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(frame)
            except:
                self.active_connections.remove(connection)

    async def broadcast_alert(self, alert_data: Dict[str, Any]):
        message = json.dumps({"type": "alert", "data": alert_data})
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()

def crop_image(image, bbox):
    x, y, width, height = map(int, bbox)
    height_img, width_img = image.shape[:2]
    x, y = max(0, x), max(0, y)
    width = min(width, width_img - x)
    height = min(height, height_img - y)
    return image[y:y+height, x:x+width]

def calculate_iou(box1, box2):
    box1_x1, box1_y1 = box1[0], box1[1]
    box1_x2, box1_y2 = box1[0] + box1[2], box1[1] + box1[3]
    box2_x1, box2_y1 = box2[0], box2[1]
    box2_x2, box2_y2 = box2[0] + box2[2], box2[1] + box2[3]
    x1, y1 = max(box1_x1, box2_x1), max(box1_y1, box2_y1)
    x2, y2 = min(box1_x2, box2_x2), min(box1_y2, box2_y2)
    if x2 < x1 or y2 < y1:
        return 0.0
    intersection = (x2 - x1) * (y2 - y1)
    union = (box1[2] * box1[3]) + (box2[2] * box2[3]) - intersection
    return intersection / union if union > 0 else 0.0

def find_best_match(protected_item, current_objects):
    best_match, best_score = None, 0
    min_score_threshold = 0.3
    for obj in current_objects:
        iou = calculate_iou(protected_item['bbox'], obj['bbox'])
        score = iou if obj['class'] == protected_item['class'] else iou * 0.8
        if score > best_score:
            best_score, best_match = score, obj
    return best_match if best_score >= min_score_threshold else None

def initialize_protection(cv2_img, detections):
    global protected_items
    protected_items = [{
        'class': d['class'],
        'bbox': d['bbox'],
        'initial_frame': crop_image(cv2_img, d['bbox']),
        'confidence': d['confidence'],
        'last_seen': time.time()
    } for d in detections if d['confidence'] > CONFIDENCE_THRESHOLD]
    return protected_items

def check_for_disturbance(cv2_img, detections):
    if not protected_items:
        return []
    disturbances = []
    for protected in protected_items:
        best_match = find_best_match(protected, detections)
        if best_match:
            iou = calculate_iou(protected['bbox'], best_match['bbox'])
            if iou < MOVEMENT_THRESHOLD:
                disturbances.append({
                    'item': protected['class'],
                    'original_bbox': protected['bbox'],
                    'current_bbox': best_match['bbox'],
                    'movement_score': 1 - iou,
                    'current_image': base64.b64encode(cv2.imencode('.jpg', crop_image(cv2_img, best_match['bbox']))[1]).decode('utf-8')
                })
        else:
            disturbances.append({
                'item': protected['class'],
                'original_bbox': protected['bbox'],
                'current_bbox': None,
                'movement_score': 1.0,
                'missing': True
            })
    return disturbances

def process_detections(frame, annotator):
    detections = frame.detections[frame.detections.confidence > CONFIDENCE_THRESHOLD]
    results = []
    labels = []
    for detection in detections:
        _, score, class_id, bbox = detection
        label = f"{model.labels[class_id]}: {score:0.2f}"
        labels.append(label)
        results.append({"class": model.labels[class_id], "confidence": score, "bbox": bbox})
    annotator.annotate_boxes(frame, detections, labels=labels)
    return results

async def process_camera_frames():
    global last_frame, protection_active, last_disturbance_check_time
    device.deploy(model)
    annotator = Annotator(thickness=1, text_thickness=1, text_scale=0.4)
    with device as stream:
        for frame in stream:
            start_time = time.time()
            detections = process_detections(frame, annotator)
            cv2_img = np.array(frame.image)[:, :, ::-1].copy() if hasattr(frame, 'image') else frame.array.copy()
            
            if protection_active and time.time() - last_disturbance_check_time > CHECK_FREQUENCY:
                disturbances = check_for_disturbance(cv2_img, detections)
                last_disturbance_check_time = time.time()
                if disturbances:
                    for d in disturbances:
                        if d.get('current_bbox'):
                            x, y, w, h = map(int, d['current_bbox'])
                            cv2.rectangle(cv2_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                            cv2.putText(cv2_img, f"ALERT: {d['item']}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    await manager.broadcast_alert({"timestamp": time.time(), "disturbances": disturbances})
            
            _, buffer = cv2.imencode('.jpg', cv2_img)
            last_frame = base64.b64encode(buffer).decode('utf-8')
            if manager.active_connections:
                await manager.broadcast_frame(last_frame)
            
            sleep_time = max(0, (1.0 / frame_rate) - (time.time() - start_time))
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            await asyncio.sleep(0)

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
                .status { margin: 10px 0; padding: 10px; background-color: #333; border-radius: 4px; }
                #alerts { max-height: 200px; overflow-y: auto; margin-top: 20px; text-align: left; padding: 10px; background-color: #333; border-radius: 4px; }
                .alert-item { margin: 5px 0; padding: 5px; border-left: 3px solid #f00; }
            </style>
        </head>
        <body>
            <h1>BagAlert Camera</h1>
            <div><img id="cameraFeed" src="" alt="Camera Feed" /></div>
            <div id="status" class="status">Connecting...</div>
            <div id="alerts"><h3>Alerts</h3><div id="alertsList"></div></div>
            <script>
                let ws;
                function connectWebSocket() {
                    ws = new WebSocket("ws://" + window.location.host + "/live");
                    ws.onopen = () => document.getElementById("status").textContent = "Connected to camera server";
                    ws.onmessage = (event) => {
                        try {
                            const jsonMsg = JSON.parse(event.data);
                            if (jsonMsg.type === "alert") {
                                displayAlert(jsonMsg.data);
                            }
                        } catch (e) {
                            document.getElementById("cameraFeed").src = "data:image/jpeg;base64," + event.data;
                        }
                    };
                    ws.onclose = () => {
                        document.getElementById("status").textContent = "Disconnected - Reconnecting...";
                        setTimeout(connectWebSocket, 2000);
                    };
                }
                function displayAlert(alertData) {
                    const alertsList = document.getElementById("alertsList");
                    const timestamp = new Date(alertData.timestamp * 1000).toLocaleTimeString();
                    alertData.disturbances.forEach(d => {
                        const alertItem = document.createElement("div");
                        alertItem.className = "alert-item";
                        alertItem.innerHTML = d.missing ? 
                            `<strong>${timestamp}</strong>: ${d.item} is MISSING` :
                            `<strong>${timestamp}</strong>: ${d.item} has moved (${Math.round(d.movement_score * 100)}% change)`;
                        alertsList.insertBefore(alertItem, alertsList.firstChild);
                    });
                }
                connectWebSocket();
            </script>
        </body>
    </html>
    """

@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    if last_frame:
        await websocket.send_text(last_frame)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/status")
async def get_status():
    return {
        "running": camera_task is not None and not camera_task.done(),
        "frame_rate": frame_rate,
        "protection_active": protection_active,
        "protected_items_count": len(protected_items)
    }

@app.get("/activate_protection")
async def activate_protection():
    global protection_active, last_frame
    if last_frame:
        img_bytes = base64.b64decode(last_frame)
        cv2_img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        with device as stream:
            frame = next(stream)
            detections = process_detections(frame, Annotator())
            initialize_protection(cv2_img, detections)
        protection_active = True
        return {"success": True, "object_count": len(protected_items)}
    return {"success": False, "message": "No frame available"}

@app.get("/deactivate_protection")
async def deactivate_protection():
    global protection_active, protected_items
    protection_active = False
    protected_items = []
    return {"success": True}

if __name__ == "__main__":
    import socket
    port = 5000
    ip_addresses = [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None) if '.' in i[4][0] and i[4][0] != '127.0.0.1'] or ['127.0.0.1']
    print("\n" + "="*80)
    print("⚡ STARTING BAGALERT CAMERA SERVER ⚡")
    print(f"Access at: {', '.join(f'http://{ip}:{port}' for ip in ip_addresses)}")
    print("="*80 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port)