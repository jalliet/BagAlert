from flask import Flask, Response, render_template
import cv2
import threading
import time
import numpy as np
import io
from PIL import Image
from modlib.apps import Annotator
from modlib.devices import AiCamera
from modlib.models.zoo import SSDMobileNetV2FPNLite320x320

app = Flask(__name__)

# Global variables for the stream
output_frame = None
lock = threading.Lock()
camera_running = False

def detect_objects():
    """
    Main function to capture the video feed, run object detection, 
    and update the global output_frame
    """
    global output_frame, lock, camera_running
    
    try:
        # Initialize the camera and model
        device = AiCamera()
        model = SSDMobileNetV2FPNLite320x320()
        
        # Deploy the model only once - this addresses the "device busy" error
        try:
            device.deploy(model)
        except RuntimeError as e:
            print(f"Warning: Failed to deploy model: {e}")
            print("Trying to continue without redeploying the model...")
        
        annotator = Annotator(thickness=1, text_thickness=1, text_scale=0.4)
        
        camera_running = True
        
        with device as stream:
            for frame in stream:
                if not camera_running:
                    break
                
                try:
                    # Run object detection
                    detections = frame.detections[frame.detections.confidence > 0.55]
                    labels = [f"{model.labels[class_id]}: {score:0.2f}" 
                             for _, score, class_id, _ in detections]
                    
                    # Annotate the frame with bounding boxes and labels
                    annotator.annotate_boxes(frame, detections, labels=labels)
                    
                    # Convert frame to cv2 image for encoding
                    # Fix: Use frame.image instead of frame.data
                    if hasattr(frame, 'image'):
                        # If frame has an image attribute, use it
                        pil_img = frame.image
                        cv2_img = np.array(pil_img)
                        # Convert RGB to BGR for OpenCV
                        if cv2_img.shape[2] == 3:
                            cv2_img = cv2_img[:, :, ::-1].copy()
                    elif hasattr(frame, 'array'):
                        # Some versions might use array instead
                        cv2_img = frame.array.copy()
                    else:
                        # Fallback: try to get image directly
                        cv2_img = np.array(frame)
                    
                    # Encode the frame in JPEG format
                    _, encoded_image = cv2.imencode('.jpg', cv2_img)
                    
                    # Update the output frame
                    with lock:
                        output_frame = encoded_image.tobytes()
                
                except Exception as e:
                    print(f"Error processing frame: {e}")
                
    except Exception as e:
        print(f"Camera thread error: {e}")
    finally:
        camera_running = False
        print("Camera stream ended")

def generate_frames():
    """
    Generator function to yield frames for the video stream
    """
    global output_frame, lock
    
    # Default frame when no camera is available
    blank_image = np.zeros((480, 640, 3), np.uint8)
    cv2.putText(blank_image, "Waiting for camera...", (50, 240), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    _, default_frame = cv2.imencode('.jpg', blank_image)
    default_frame = default_frame.tobytes()
    
    while True:
        # Wait until we have a frame
        with lock:
            if output_frame is None:
                frame_copy = default_frame
            else:
                # bytes objects don't have a copy method, just use the object directly
                frame_copy = output_frame
        
        # Yield the frame in multipart/x-mixed-replace format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_copy + b'\r\n')
        
        # Small sleep to control frame rate
        time.sleep(0.03)  # About 30 FPS

@app.route('/')
def index():
    """Serve the index page"""
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    """
    Route for streaming the video feed
    """
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera')
def start_camera():
    """Start the camera thread if it's not already running"""
    global camera_running
    
    if not camera_running:
        thread = threading.Thread(target=detect_objects)
        thread.daemon = True
        thread.start()
        return "Camera started"
    return "Camera is already running"

@app.route('/stop_camera')
def stop_camera():
    """Stop the camera thread"""
    global camera_running
    camera_running = False
    return "Camera stopped"

@app.route('/status')
def status():
    """Return the status of the camera"""
    global camera_running
    return {"running": camera_running}

if __name__ == '__main__':
    # Create a directory for templates if it doesn't exist
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create a simple HTML template for viewing the stream
    with open('templates/index.html', 'w') as f:
        f.write("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ModLib Camera Stream</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin: 20px; background-color: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                .video-container { margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }
                .controls { margin: 20px 0; }
                button { padding: 10px 20px; margin: 0 10px; cursor: pointer; background-color: #4CAF50; color: white; border: none; border-radius: 5px; }
                button:hover { background-color: #45a049; }
                .status { margin-top: 10px; font-style: italic; color: #666; }
                h1 { color: #333; }
                .info { font-size: 14px; margin-top: 20px; text-align: left; background-color: #f9f9f9; padding: 10px; border-radius: 5px; }
            </style>
            <script>
                // Check camera status every 3 seconds
                function checkStatus() {
                    fetch('/status')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('status').innerText = 
                                data.running ? 'Camera is running' : 'Camera is stopped';
                        });
                }
                
                // Start checking status when page loads
                window.onload = function() {
                    checkStatus();
                    setInterval(checkStatus, 3000);
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h1>ModLib Camera Stream</h1>
                <div class="video-container">
                    <img src="{{ url_for('video_feed') }}" width="100%">
                </div>
                <div class="controls">
                    <button onclick="fetch('/start_camera').then(() => checkStatus())">Start Camera</button>
                    <button onclick="fetch('/stop_camera').then(() => checkStatus())">Stop Camera</button>
                </div>
                <div class="status" id="status">Checking camera status...</div>
                <div class="info">
                    <p><strong>Network Info:</strong> This stream is accessible at:</p>
                    <ul>
                        <li>http://127.0.0.1:5000 (local access)</li>
                        <li>http://[your-ip-address]:5000 (same network access)</li>
                    </ul>
                    <p>To view from another device, enter the above URL in your browser.</p>
                </div>
            </div>
        </body>
        </html>
        """)
    
    print("Starting camera server...")
    print("Access the stream from other devices at: http://[your-ip-address]:5000")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)