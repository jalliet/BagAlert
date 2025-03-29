import paho.mqtt.client as mqtt

client = mqtt.Client()
IP_ADDRESS = "YOUR_IP_ADDRESS"
client.connect(IP_ADDRESS, 1883, 60)  # Change 'localhost' to Raspberry Pi's IP if needed

client.publish("test/topic", "Hello from Python!")
print("Message sent!")
