import paho.mqtt.client as mqtt
import requests
import time

# MQTT Broker settings
BROKER = "YOUR_IP_ADDRESS"  # Replace with your laptop's IP on the mobile hotspot
PORT = 1883
TOPIC = "esp/messages"

# FastAPI server settings
CAMERA_SERVER = "http://localhost:5000"

# Track active users
active_users = set()
last_status_check = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    user_id = msg.payload.decode().strip()
    print(f"RFID detected: {user_id}")
    
    global active_users
    
    if user_id in active_users:
        # User is checking out - deactivate protection
        active_users.remove(user_id)
        print(f"User {user_id} removed from active protection")
        
        # If this was the last active user, stop protection
        if len(active_users) == 0:
            # Deactivate protection in the server
            try:
                response = requests.get(f"{CAMERA_SERVER}/deactivate_protection")
                if response.status_code == 200:
                    print("Protection deactivated successfully")
                else:
                    print(f"Error deactivating protection: HTTP {response.status_code}")
            except Exception as e:
                print(f"Error communicating with camera server: {e}")
    else:
        # New user checking in - activate protection
        active_users.add(user_id)
        print(f"User {user_id} added to active protection")
        
        # If this is the first active user, start protection
        if len(active_users) == 1:
            # Activate protection in the server
            try:
                response = requests.get(f"{CAMERA_SERVER}/activate_protection")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        print(f"Protection activated! Monitoring {data.get('object_count')} objects")
                    else:
                        print(f"Failed to activate protection: {data.get('message')}")
            except Exception as e:
                print(f"Error communicating with camera server: {e}")

def periodic_check(client):
    """
    Periodically check the protection status
    This function is called regularly by the MQTT client loop
    """
    global last_status_check, active_users
    current_time = time.time()
    
    # Check status every 5 seconds if we have active users
    if len(active_users) > 0 and current_time - last_status_check > 5:
        try:
            # Check status to make sure protection is still active
            response = requests.get(f"{CAMERA_SERVER}/status")
            if response.status_code == 200:
                data = response.json()
                if not data.get('protection_active') and len(active_users) > 0:
                    print("Warning: Protection inactive on server. Reactivating...")
                    requests.get(f"{CAMERA_SERVER}/activate_protection")
            
            last_status_check = current_time
            
        except Exception as e:
            print(f"Error in status check: {e}")

# Set up MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"Connecting to MQTT broker at {BROKER}:{PORT}...")
try:
    client.connect(BROKER, PORT, 60)
    
    # Use callback-based loop instead of loop_forever()
    client.loop_start()
    
    # Main program loop
    try:
        while True:
            # Perform periodic status checks
            periodic_check(client)
            # Sleep a short interval
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nMQTT subscriber stopped by user")
    finally:
        # Clean up
        if len(active_users) > 0:
            print("Deactivating protection before exit...")
            try:
                requests.get(f"{CAMERA_SERVER}/deactivate_protection")
            except:
                pass
        client.loop_stop()
        
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")