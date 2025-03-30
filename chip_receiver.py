import requests
import time

esp32_ip = "http://192.168.4.1/"

while True:
    connected_uid = ""
    try:
        response = requests.get(esp32_ip, timeout=2)
        uid = response.text.strip()
        if uid != connected_uid:
            connected_uid = uid
            print("Reset UID:", uid)
        if connected_uid == uid:
            connected_uid = ""
            print("Removed UID:", uid)
    except Exception as e:
        print("Error:", e)
    time.sleep(1)