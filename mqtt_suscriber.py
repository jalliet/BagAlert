import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    print(f"Received RFID Tag: {msg.payload.decode()}")

IP_ADDRESS = "YOUR_IP_ADDRESS"

client = mqtt.Client()
client.connect(IP_ADDRESS, port=1883, keepalive=60)

client.subscribe("test/topic")
client.on_message = on_message

client.loop_forever()
