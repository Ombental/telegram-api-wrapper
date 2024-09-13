from telegram_api_wrapper import Bot
from telegram_api_wrapper.buttons import InlineButton
from telegram_api_wrapper.keyboard import InlineKeyboardMarkup, ReplyKeyboardMarkup


def telegram_bot(data):
    bot = Bot(data)

    if bot.is_callback_query:
        if bot.is_picking_date and not bot.finished_picking_date:
            bot.continue_picking_date()
        else:
            if bot.callback_query_data == "123":
                reply_keyboard = [[InlineButton("awww naww", 3)]]
                keyboard = InlineKeyboardMarkup(reply_keyboard)
                bot.edit_inline_message("this is 123", keyboard)
            elif bot.callback_query_data == "3":
                bot.edit_inline_message("this is 3")
            else:
                bot.edit_inline_message("this is None")

        chosen_date = bot.get_picked_date()
        if chosen_date:
            bot.send_message(f"You chose a date! {chosen_date}")
    else:
        if bot.message_text == "/start":
            reply_keyboard = [["/help"], ["/woot"], ["/previous"]]
            keyboard = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
            bot.send_message("Pick & Choose", keyboard)
        elif bot.message_text == "/woot":
            reply_keyboard = [[InlineButton("woa", 123), InlineButton("awww", 3)]]
            keyboard = InlineKeyboardMarkup(reply_keyboard)
            bot.send_message("Pick & Choose", keyboard)
        elif bot.message_text == "/previous":
            bot.send_message(f"Previous message: {bot.context.get('previous_message')}")
        elif bot.message_text == "/calendar":
            bot.start_picking_date()
        else:
            bot.update_context({"previous_message": bot.message_text})
            bot.send_message(f"Echo: {bot.message_text}")
    return "OK"


if __name__ == "__main__":
    while True:
        update = Bot.get_single_update()
        print(update)
        if update:
            telegram_bot(update)
