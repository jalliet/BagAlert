# Pseudocode for object recognition and monitoring

import cv2
import numpy as np
from modlib.apps import Annotator
from modlib.devices import AiCamera
from modlib.models.zoo import SSDMobileNetV2FPNLite320x320

# Configuration
MOVEMENT_THRESHOLD = 0.6  # IoU threshold - below this triggers alert
CHECK_FREQUENCY = 1  # Check every N seconds
CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence for object detection

# Storage for protected items
protected_items = []

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

def initialize_protection(image):
    """When user locks their belongings, detect and catalog objects"""
    objects = detect_objects(image)  # This would use the IMX500's detection capabilities
    
    for obj in objects:
        if obj['confidence'] > CONFIDENCE_THRESHOLD:
            protected_items.append({
                'class': obj['class'],
                'bbox': obj['bbox'],  # [x, y, width, height]
                'initial_image': crop_image(image, obj['bbox']),
                'last_seen_bbox': obj['bbox'],
                'confidence': obj['confidence'],
            })
    
    return len(protected_items)

def process_frame(frame, model, annotator):
    """
    Process a single frame: run object detection and return detections.
    Also annotate the frame.
    """
    detections = frame.detections[frame.detections.confidence > 0.55]
    detection_results = []
    labels = []
    for detection in detections:
        _, score, class_id, bbox = detection
        label = f"{model.labels[class_id]}: {score:0.2f}"
        labels.append(label)
        detection_results.append({
            "class": model.labels[class_id],
            "confidence": score,
            "bbox": bbox  # Adjust format as needed
        })
    
    # Annotate the frame for visual output
    annotator.annotate_boxes(frame, detections, labels=labels)
    return detection_results

def detect_objects():
    """
    Runs continuously to process frames. Updates the global output_frame for streaming
    and publishes detection results (if needed) via MQTT/WebSocket.
    """
    global output_frame, lock, camera_running
    try:
        device = AiCamera()
        model = SSDMobileNetV2FPNLite320x320()
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
                    # Process the frame to get detection data
                    detection_results = process_frame(frame, model, annotator)
                    
                    # Convert frame to cv2 image for encoding
                    if hasattr(frame, 'image'):
                        pil_img = frame.image
                        cv2_img = np.array(pil_img)
                        if cv2_img.shape[2] == 3:
                            cv2_img = cv2_img[:, :, ::-1].copy()
                    elif hasattr(frame, 'array'):
                        cv2_img = frame.array.copy()
                    else:
                        cv2_img = np.array(frame)
                    
                    _, encoded_image = cv2.imencode('.jpg', cv2_img)
                    with lock:
                        output_frame = encoded_image.tobytes()
                    
                    # Here, instead of returning, you could publish detection_results via MQTT/WebSocket:
                    # mqtt_client.publish("camera/detections", json.dumps({
                    #     "timestamp": time.time(),
                    #     "detections": detection_results
                    # }))
                    
                except Exception as e:
                    print(f"Error processing frame: {e}")
    
    except Exception as e:
        print(f"Camera thread error: {e}")
    
    finally:
        camera_running = False
        print("Camera stream ended")

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
        
        # We could also consider combining IoU with other metrics like:
        # - Visual similarity (if you compute feature vectors)
        # - Size similarity
        # - Position relative to other objects
        
        if iou > best_score:
            best_score = iou
            best_match = obj
    
    # If we didn't find a good match with the same class,
    # we could optionally look for objects of different classes
    # (in case the object was misclassified in the new frame)
    if best_score < min_score_threshold:
        for obj in current_objects:
            if obj['class'] != protected_item['class']:
                iou = calculate_iou(protected_item['bbox'], obj['bbox'])
                # Maybe apply a penalty for different class
                adjusted_score = iou * 0.8  # 20% penalty for class mismatch
                
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_match = obj
    
    # If the match is too poor, return None
    if best_score < min_score_threshold:
        return None
        
    return best_match


def check_for_disturbance(current_image):
    """Check if protected objects have moved"""
    current_objects = detect_objects(current_image)
    disturbances = []
    
    for protected in protected_items:
        best_match = find_best_match(protected, current_objects)
        
        if best_match:
            # Calculate IoU between original and current position
            iou = calculate_iou(protected['bbox'], best_match['bbox'])
            
            if iou < MOVEMENT_THRESHOLD:
                disturbances.append({
                    'item': protected['class'],
                    'original_bbox': protected['bbox'],
                    'current_bbox': best_match['bbox'],
                    'movement_score': 1 - iou,
                    'current_image': crop_image(current_image, best_match['bbox'])
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