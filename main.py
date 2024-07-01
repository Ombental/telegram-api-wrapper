from flask import Flask, request

from bot import Bot
from buttons import InlineButton
from keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup

app = Flask(__name__)


@app.route("/", methods=["POST"])
def telegram_bot():
    data = request.get_json()
    bot = Bot(data)
    if bot.is_callback_query:
        if bot.callback_query_data == "123":
            reply_keyboard = [[InlineButton("awww naww", 3)]]
            keyboard = InlineKeyboardMarkup(reply_keyboard)
            bot.edit_inline_message("this is 123", keyboard)
        elif bot.callback_query_data == "3":
            bot.edit_inline_message("this is 3")
        else:
            bot.edit_inline_message("this is None")
    else:
        if bot.message_text == "/start":
            reply_keyboard = [["/help"], ["/woot"]]
            keyboard = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
            bot.send_message("Pick & Choose", keyboard)
        elif bot.message_text == "/woot":
            reply_keyboard = [[InlineButton("woa", 123), InlineButton("awww", 3)]]
            keyboard = InlineKeyboardMarkup(reply_keyboard)
            bot.send_message("Pick & Choose", keyboard)
        else:
            bot.send_message(f"Echo: {bot.message_text}")
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
