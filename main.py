import logging
from typing import List
import time
from fastapi import FastAPI
from redis import Redis
import random
import json
from datetime import datetime
import paho.mqtt.client as mqtt

from app.adapters.store_api_adapter import StoreApiAdapter
from app.entities.agent_data import AgentData, AccelerometerData, GpsData
from app.entities.processed_agent_data import ProcessedAgentData
from config import (
    STORE_API_BASE_URL,
    REDIS_HOST,
    REDIS_PORT,
    BATCH_SIZE,
    MQTT_TOPIC,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
)

# Configure logging settings
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO (you can use logging.DEBUG for more detailed logs)
    format="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
    handlers=[
        logging.StreamHandler(),  # Output log messages to the console
        logging.FileHandler("app.log"),  # Save log messages to a file
    ],
)
# Create an instance of the Redis using the configuration
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT)
# Create an instance of the StoreApiAdapter using the configuration
store_adapter = StoreApiAdapter(api_base_url=STORE_API_BASE_URL)
# Create an instance of the AgentMQTTAdapter using the configuration

# FastAPI
app = FastAPI()


@app.post("/processed_agent_data/")
async def save_processed_agent_data(processed_agent_data: ProcessedAgentData):
    redis_client.lpush("processed_agent_data", processed_agent_data.model_dump_json())
    if redis_client.llen("processed_agent_data") >= BATCH_SIZE:
        processed_agent_data_batch: List[ProcessedAgentData] = []
        for _ in range(BATCH_SIZE):
            processed_agent_data = ProcessedAgentData.model_validate_json(
                redis_client.lpop("processed_agent_data")
            )
            processed_agent_data_batch.append(processed_agent_data)
        store_adapter.save_data(processed_agent_data_batch=processed_agent_data_batch)
    return {"status": "ok"}


# MQTT
client = mqtt.Client()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.info(f"Failed to connect to MQTT broker with code: {rc}")


def on_message(client, userdata, msg):
    try:
        payload: str = msg.payload.decode("utf-8")
        # Create ProcessedAgentData instance with the received data
        processed_agent_data = ProcessedAgentData.model_validate_json(
            payload, strict=True
        )
        redis_client.lpush(
            "processed_agent_data", processed_agent_data.model_dump_json()
        )
        logging.info(f"You have a notification that something has been added to redis")
        if redis_client.llen("processed_agent_data") >= BATCH_SIZE:
            processed_agent_data_batch: List[ProcessedAgentData] = []
            for _ in range(BATCH_SIZE):
                processed_agent_data = ProcessedAgentData.model_validate_json(
                    redis_client.lpop("processed_agent_data")
                )
                processed_agent_data_batch.append(processed_agent_data)
            store_adapter.save_data(processed_agent_data_batch=processed_agent_data_batch)
            logging.info(f"Saved {BATCH_SIZE} notification to postgres_db")
        return {"status": "ok"}
    except Exception as e:
        logging.info(f"Error processing MQTT message: {e}")

def publish(client, topic):
    while True:
        processed_data = {"road_state": random.choice(["good", "bad"]), "agent_data":
            {
                "accelerometer": {"x": random.uniform(0, 10), "y": random.uniform(0, 10), "z": random.uniform(0, 10)},
                "gps": {"latitude": random.uniform(-90, 90), "longitude": random.uniform(-90, 90)},
                "timestamp": "2024-03-15T14:34:20.236457"
            }
                          }
        json_string = json.dumps(processed_data)
        client.publish(topic, payload=json_string)
        time.sleep(1)


# Connect
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)

# Start
client.loop_start()
publish(client=client, topic=MQTT_TOPIC)
