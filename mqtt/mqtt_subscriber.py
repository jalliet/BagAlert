import paho.mqtt.client as mqtt
import requests
import time

# Configuration
BROKER = "YOUR_IP_ADDRESS"  # Replace with your MQTT broker IP
PORT = 1883
TOPIC = "esp/messages"
CAMERA_SERVER = "http://localhost:5000"

# Global state
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
    
    if user_id in active_users:
        active_users.remove(user_id)
        print(f"User {user_id} removed")
        if not active_users:
            try:
                response = requests.get(f"{CAMERA_SERVER}/deactivate_protection")
                print("Protection deactivated" if response.status_code == 200 else f"Deactivation failed: HTTP {response.status_code}")
            except Exception as e:
                print(f"Error deactivating protection: {e}")
    else:
        active_users.add(user_id)
        print(f"User {user_id} added")
        if len(active_users) == 1:
            try:
                response = requests.get(f"{CAMERA_SERVER}/activate_protection")
                if response.status_code == 200 and response.json().get('success'):
                    print(f"Protection activated! Monitoring {response.json().get('object_count')} objects")
                else:
                    print(f"Activation failed: {response.json().get('message')}")
            except Exception as e:
                print(f"Error activating protection: {e}")

def periodic_check(client):
    global last_status_check
    if active_users and time.time() - last_status_check > 5:
        try:
            response = requests.get(f"{CAMERA_SERVER}/status")
            if response.status_code == 200 and not response.json().get('protection_active') and active_users:
                print("Warning: Protection inactive. Reactivating...")
                requests.get(f"{CAMERA_SERVER}/activate_protection")
            last_status_check = time.time()
        except Exception as e:
            print(f"Status check error: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

print(f"Connecting to MQTT broker at {BROKER}:{PORT}...")
try:
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    while True:
        periodic_check(client)
        time.sleep(0.5)
except Exception as e:
    print(f"Failed to connect: {e}")
finally:
    if active_users:
        try:
            requests.get(f"{CAMERA_SERVER}/deactivate_protection")
        except:
            pass
    client.loop_stop()