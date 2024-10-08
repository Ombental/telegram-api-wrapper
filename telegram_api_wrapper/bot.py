import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from time import sleep
from typing import Optional, Union
from urllib.parse import urljoin

import boto3
import requests
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from telegram_api_wrapper.calendar_util import _picked_year, _process_calendar_step, _send_year_choices
from telegram_api_wrapper.keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup


@dataclass
class Bot:
    """
    Local and Lambda ready
    """
    base_url: str
    sender_name: str
    chat_id: int
    message_text: str
    message_id: str
    callback_query_id: int
    is_callback_query: bool = False
    is_picking_date: bool = False
    finished_picking_date: bool = False
    callback_query_data: Optional[str] = None

    SEND_MESSAGE = "sendMessage"
    ANSWER_CALLBACK_QUERY = "answerCallbackQuery"
    EDIT_MESSAGE_TEXT = "editMessageText"
    GET_UPDATES = "getUpdates"

    UPDATE_FILE_NAME = "update_offset.json"
    CHAT_KEY_NAME = "chats"
    IS_DATE_PICKING_CONTEXT_PREFIX = "is_picking_date_for_"
    PICKED_DATE_CONTEXT_PREFIX = "picked_date_for_"

    def __init__(self, message, context_storage=None):
        self.base_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_API_TOKEN']}/"
        self.context_storage = context_storage if context_storage else os.environ.get(
            "TELEGRAM_BOT_CONTEXT_STORAGE", "context.json")
        self.file_based_backend = not bool(os.environ.get("DYNAMO_DB_BASED_BACKEND", False))

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
        self.context = self._load_chat_context()

        self.is_picking_date = self.is_callback_query and self.context.get(
            f"{self.IS_DATE_PICKING_CONTEXT_PREFIX}{self.message_id}",
            False)

        if self.is_callback_query and _picked_year(str(self.callback_query_data)):
            self.update_context({
                f"{self.IS_DATE_PICKING_CONTEXT_PREFIX}{self.message_id}": True,
                f"{self.PICKED_DATE_CONTEXT_PREFIX}{self.message_id}": {}
            })
            self.is_picking_date = True

        if self.is_picking_date:
            picked_date_parts = self.context.get(f"{self.PICKED_DATE_CONTEXT_PREFIX}{self.message_id}", {})
            self.finished_picking_date = all(
                part in picked_date_parts and picked_date_parts[part] for part in ["day", "month", "year"])

    def update_context(self, context_update):
        """
                    use chat id to set to a json file prolly
                    need to think about race conditions
        """
        if not self.file_based_backend:
            table = boto3.resource('dynamodb').Table(self.context_storage)
            self.context.update(context_update)

            item = {
                'ChatID': str(self.chat_id),
                'Context': self.context
            }
            table.put_item(
                Item=item
            )
        else:
            with open(self.context_storage, "r") as f:
                data = json.load(f)

            if self.CHAT_KEY_NAME not in data:
                data[self.CHAT_KEY_NAME] = {}

            self.context.update(context_update)
            data[self.CHAT_KEY_NAME][str(self.chat_id)] = self.context
            with open(self.context_storage, "w") as f:
                json.dump(data, f)

    def _load_chat_context(self):
        """
            use chat id to get from a json file prolly
            need to think about race conditions
        """
        if not self.file_based_backend:
            table = boto3.resource('dynamodb').Table(self.context_storage)
            response = table.query(
                KeyConditionExpression=Key('ChatID').eq(str(self.chat_id))
            )
            context = {}
            if int(response.get("Count", 0)) == 0:
                item = {
                    'ChatID': str(self.chat_id),
                    'Context': {}
                }
                table.put_item(
                    Item=item
                )
            else:
                items = response.get('Items', [{}])
                context = items[0].get('Context', {})
            return context
        if not os.path.exists(self.context_storage):
            with open(self.context_storage, "w") as f:
                json.dump({}, f)
        with open(self.context_storage, "r") as f:
            return json.load(f).get(self.CHAT_KEY_NAME, {}).get(str(self.chat_id), {})

    def _answer_callback(self):
        api_url = urljoin(self.base_url, self.ANSWER_CALLBACK_QUERY)
        try:
            data = {"callback_query_id": self.callback_query_id}
            requests.post(api_url, json=data)
        except Exception as e:
            print(e)

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
        """
        We assume this is a "local only" type of call, so no handling of "non file backend"
        """
        sleep(1)
        if not os.path.exists(cls.UPDATE_FILE_NAME):
            with open(cls.UPDATE_FILE_NAME, "w") as f:
                json.dump({
                    "offset": 1,
                }, f, indent=4)
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

    def start_picking_date(self, message_text: str = "בחירת תאריך"):
        keyboard = _send_year_choices()
        self.send_message(message_text, keyboard)

    def continue_picking_date(self):
        # if this is the last pick stage
        if self.finished_picking_date:
            # should we raise error?
            return
        _process_calendar_step(self)

    def get_picked_date(self):
        if self.is_picking_date and self.finished_picking_date:
            return date(**{key: int(value) for key, value in
                                    self.context[f"{self.PICKED_DATE_CONTEXT_PREFIX}{self.message_id}"].items()})
        # This means that date shouldn't be available yet
        return False
