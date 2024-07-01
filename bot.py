import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Union
from urllib.parse import urljoin

import requests

from keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup


@dataclass
class Bot:
    base_url: str
    storage: str
    latest_update_id: int
    latest_update_date: datetime
    sender_name: str
    chat_id: int
    message_text: str
    message_id: str
    callback_query_id: int
    is_callback_query: bool = False
    callback_query_data: Optional[str] = None

    SEND_MESSAGE = "sendMessage"
    ANSWER_CALLBACK_QUERY = "answerCallbackQuery"
    EDIT_MESSAGE_TEXT = "editMessageText"
    GET_UPDATES = "getUpdates"

    UPDATE_FILE_NAME = "update_offset.json"

    def __init__(self, message, storage: str = "storage.json"):
        self.base_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_API_TOKEN']}/"
        self.storage = storage
        self._load_state_from_storage()
        update_id = message.get("update_id")
        # if self.latest_update_id > update_id:
        #     raise BotUpdateOrderError(
        #         f"{self.latest_update_id} is greater than the latest update id - {update_id}"
        #     )
        self._update_state(update_id)
        if "message" in message:
            message = message["message"]
        elif "callback_query" in message:
            callback_query = message["callback_query"]
            message = message["callback_query"]["message"]
            self.is_callback_query = True
            self.callback_query_data = callback_query["data"]
            self.callback_query_id = callback_query["id"]
            self._answer_callback()
        self.sender_name = message["from"].get("first_name", "")
        self.chat_id = message["chat"]["id"]
        self.message_text = message.get("text", "")
        self.message_id = message["message_id"]

    def _answer_callback(self):
        api_url = urljoin(self.base_url, self.ANSWER_CALLBACK_QUERY)
        try:
            data = {"callback_query_id": self.callback_query_id}
            requests.post(api_url, json=data)
        except Exception as e:
            print(e)

    def _update_state(self, update_id):
        with open(self.storage, "w") as f:
            update_time = datetime.utcnow()
            d = {
                "latest_update_id": update_id,
                "latest_update_time": update_time.timestamp(),
            }
            json.dump(d, f, indent=4)
            self.latest_update_id = update_id
            self.latest_update_time = update_time

    def _load_state_from_storage(self):
        if not os.path.exists(self.storage):
            self._update_state(0)
        with open("storage.json", "r") as storage:
            states = json.load(storage)
            self.latest_update_id = states["latest_update_id"]
            self.latest_update_time = datetime.fromtimestamp(
                states["latest_update_time"]
            )
        if self.latest_update_time + timedelta(days=7) < datetime.utcnow():
            self._update_state(0)

    def send_message(
        self,
        text,
        rmarkup: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None,
    ):
        api_url = urljoin(self.base_url, self.SEND_MESSAGE)
        try:
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            if rmarkup is not None:
                data["reply_markup"] = rmarkup.to_json()
            else:
                data["reply_markup"] = {"remove_keyboard": True}
            requests.post(api_url, json=data)
        except Exception as e:
            print(e)

    def edit_inline_message(
        self, text: Optional[str] = None, rmarkup: Optional[InlineKeyboardMarkup] = None
    ):
        if not self.is_callback_query:
            raise ValueError("edit_inline_message called without callback query")
        if text is None:
            text = self.message_text
        api_url = urljoin(self.base_url, self.EDIT_MESSAGE_TEXT)
        try:
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "message_id": self.message_id,
            }
            if rmarkup is not None:
                data["reply_markup"] = rmarkup.to_json()
            requests.post(api_url, json=data)
        except Exception as e:
            print(e)

    @classmethod
    def get_single_update(cls):
        api_url = urljoin(f"https://api.telegram.org/bot{os.environ['TELEGRAM_API_TOKEN']}/", cls.GET_UPDATES)
        with open(cls.UPDATE_FILE_NAME, "r") as f:
            states = json.load(f)
            latest_offset = int(states["offset"])
        data = {"limit": 1, "offset": latest_offset}
        response = requests.post(api_url, json=data)
        res_data = response.json()
        result = res_data["result"]
        if result:
            result = result[0]
            with open(cls.UPDATE_FILE_NAME, "w") as f:
                json.dump({
                    "offset": result["update_id"] + 1,
                }, f, indent=4)
            return result
