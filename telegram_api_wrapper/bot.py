import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import sleep
from typing import Optional, Union
from urllib.parse import urljoin

import boto3
import requests
from botocore.exceptions import ClientError

from telegram_api_wrapper.keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup


@dataclass
class Bot:
    """
    Local and Lambda ready
    """
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
    CHAT_KEY_NAME = "chats"

    def __init__(self, message, storage, context_storage):
        self.base_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_API_TOKEN']}/"
        self.storage = storage if storage else os.environ.get("TELEGRAM_BOT_STORAGE", "storage.json")
        self.context_storage = context_storage if context_storage else os.environ.get(
            "TELEGRAM_BOT_CONTEXT_STORAGE", "context.json")
        self.file_based_backend = not bool(os.environ.get("DYNAMO_DB_BASED_BACKEND", False))
        self._load_state_from_storage()
        update_id = message.get("update_id")

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
        self.context = self._load_chat_context()

    def update_context(self, context_update):
        """
                    use chat id to set to a json file prolly
                    need to think about race conditions
        """
        if not self.file_based_backend:
            table = boto3.resource('dynamodb').Table(self.context_storage)
            self.context.update(context_update)

            item = {
                'chat_id': str(self.chat_id),
                'context': json.dumps(self.context)
            }

            try:
                response = table.put_item(
                    Item=item,
                    ConditionExpression='attribute_exists(chat_id)'
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    # Handle the case where the item doesn't exist
                    response = table.put_item(Item=item)
                    print(response)
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
            response = table.get_item(
                Key={'chat_id': str(self.chat_id)}
            )

            item = response.get('Item', {})
            context = json.loads(item.get('context', '{}'))
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

    def _update_state(self, update_id):
        update_time = datetime.utcnow()
        if not self.file_based_backend:
            table = boto3.resource('dynamodb').Table(self.storage)
            item = {
                'name': 'last_update_time',
                'latest_update_id': update_id,
                'latest_update_time': update_time.timestamp(),
            }
            table.put_item(Item=item)
            self.latest_update_id = update_id
            self.latest_update_time = update_time
        else:
            with open(self.storage, "w") as f:
                d = {
                    "latest_update_id": update_id,
                    "latest_update_time": update_time.timestamp(),
                }
                json.dump(d, f, indent=4)
                self.latest_update_id = update_id
                self.latest_update_time = update_time

    def _load_state_from_storage(self):
        if not self.file_based_backend:
            table = boto3.resource('dynamodb').Table(self.storage)
            response = table.get_item(
                Key={'name': 'last_update_time'}  # Assuming chat_id is set elsewhere
            )

            # Handle the case where no record exists
            if 'Item' not in response:
                self._update_state(0)
                return

            item = response['Item']
            self.latest_update_id = item['latest_update_id']
            self.latest_update_time = datetime.fromtimestamp(item['latest_update_time'])

            # Check for outdated state and update if necessary
            if self.latest_update_time + timedelta(days=7) < datetime.utcnow():
                self._update_state(0)
        else:
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
