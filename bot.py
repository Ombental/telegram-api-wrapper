import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests

from errors import BotUpdateOrderError
from keyboard import ReplyKeyboardMarkup


@dataclass
class Bot:
    api_token: str
    storage: str
    latest_update_id: int
    latest_update_date: datetime
    sender_name: str
    chat_id: int
    message_text: str

    def __init__(self, message, storage: str = "storage.json"):
        self.api_token = os.environ['TELEGRAM_API_TOKEN']
        self.storage = storage
        self._load_state_from_storage()
        update_id = message.get('update_id')
        if self.latest_update_id > update_id:
            raise BotUpdateOrderError(f"{update_id} is greater than the latest update id - {self.latest_update_id}")
        self._update_state(update_id)
        message = message.get('message')
        self.sender_name = message['from'].get('first_name', '')
        self.chat_id = message['chat']['id']
        self.message_text = message.get('text', '')

    def _update_state(self, update_id):
        with open(self.storage, 'w') as f:
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
            self.latest_update_id = states['latest_update_id']
            self.latest_update_time = datetime.fromtimestamp(states['latest_update_time'])
        if self.latest_update_time + timedelta(days=7) < datetime.utcnow():
            self._update_state(0)

    def send_message(self, text, rmarkup: Optional[ReplyKeyboardMarkup] = None):
        print('sending message - check deploy')
        print(text, rmarkup, self.chat_id)
        api_url = f'https://api.telegram.org/bot{self.api_token}/sendMessage'
        try:
            data = {'chat_id': self.chat_id, 'text': text, 'parse_mode': 'HTML'}
            if rmarkup is not None:
                data['reply_markup'] = rmarkup.to_json()
            else:
                data['reply_markup'] = {
                    'remove_keyboard': True
                }
            response = requests.post(api_url, json=data)
            print(response.text)
        except Exception as e:
            print(e)

    # def build_message(message_body, chat_id):
    #     res = login(chat_id, message_body)
    #     if isinstance(res, tuple):
    #         return res
    #     person_name = res
    #     message_text = message_body.get('text', '')
    #     response_message = 'קרתה תקלה', None
    #
    #     # TODO: maybe send a message to telegram from here as well (like - "WORKING/LOADING")
    #     if 'סיכום' in message_text:
    #         response_message = get_summary_expenses(person_name)
    #     elif message_text.isdecimal():
    #         response_message = get_last_expenses(person_name, int(message_text))
    #     else:
    #         response_message = get_last_expenses(person_name, category=message_text)
    #     return response_message
