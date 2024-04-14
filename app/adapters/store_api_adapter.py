import json
import logging
from typing import List

import requests
from app.entities.processed_agent_data import ProcessedAgentData
from app.interfaces.store_gateway import StoreGateway


class StoreApiAdapter(StoreGateway):
    def __init__(self, api_base_url):
        self.api_base_url = api_base_url

    def save_data(self, processed_agent_data_batch: List[ProcessedAgentData]) -> bool:

        data = [json.loads(item.model_dump_json()) for item in processed_agent_data_batch]

        response = requests.post(f"{self.api_base_url}/processed_agent_data/", json=data)
        return response.status_code == requests.codes.ok