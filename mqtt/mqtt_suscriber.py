import paho.mqtt.client as mqtt

# MQTT Broker settings
BROKER = "YOUR_IP_ADDRESS"  # Replace with your laptop's IP on the mobile hotspot
PORT = 1883
TOPIC = "esp/messages"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe(TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    print(f"{msg.payload.decode()}")

# Set up MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)

# Keep listening for messages
client.loop_forever()