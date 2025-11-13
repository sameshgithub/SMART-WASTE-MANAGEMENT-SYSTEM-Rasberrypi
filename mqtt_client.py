"""
mqtt_client.py
Simple MQTT publisher that can be used to push sensor readings to a broker.
"""

import json
import time
from paho.mqtt import client as mqtt_client

BROKER = "your.mqtt.broker"
PORT = 1883
TOPIC_BASE = "smartwaste"
CLIENT_ID = "smartwaste-pi-1"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print("Failed to connect, return code %d\n", rc)

def publish_level(client, bin_id, payload):
    topic = f"{TOPIC_BASE}/{bin_id}/level"
    client.publish(topic, json.dumps(payload), qos=1)

def run_publisher():
    client = mqtt_client.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()
    # usage: publish_level(client, "bin_1", {"level": 63.5, "timestamp": int(time.time())})
    return client
