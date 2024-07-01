from flask import Flask, jsonify, request

from bot import Bot
from keyboard import ReplyKeyboardMarkup

app = Flask(__name__)


@app.route('/', methods=['POST'])
def telegram_bot():
    data = request.get_json()
    bot = Bot(data)
    print(data)
    if bot.message_text == "/start":
        reply_keyboard = [["/help", "/start"]]
        keyboard = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        bot.send_message("Pick & Choose", keyboard)
    else:
        bot.send_message(f"Echo: {bot.message_text}")
    return "OK"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
