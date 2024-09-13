import calendar
import locale
from datetime import date

from telegram_api_wrapper.buttons import InlineButton
from telegram_api_wrapper.keyboard import InlineKeyboardMarkup

DELIMITER = ";"
YEAR_PREFIX = "year"
MONTH_PREFIX = "month"
DAY_PREFIX = "day"
CANCEL_BUTTON = "cancel"
RETURN_BUTTON = "return"


def _picked_year(data: str):
    return data.startswith(f"{YEAR_PREFIX}{DELIMITER}")


def _send_year_choices():
    year = date.today().year
    reply_keyboard = [[InlineButton(str(y), f"{YEAR_PREFIX}{DELIMITER}{y}") for y in range(year - 1, year + 2)]]
    return InlineKeyboardMarkup(reply_keyboard)


def _send_month_choices():
    try:
        locale.setlocale(locale.LC_ALL, 'he_IL.utf8')
    finally:
        reply_keyboard = []
        temp = []
        for i, month in enumerate(calendar.month_abbr[1:]):
            if i % 4 == 0 and i > 0:
                reply_keyboard.append(temp[::-1])
                temp = []
            temp.append(InlineButton(str(month).replace("'", ""), f"{MONTH_PREFIX}{DELIMITER}{i + 1}"))
        reply_keyboard.append(temp[::-1])
        reply_keyboard.append(
            [InlineButton("ביטול", CANCEL_BUTTON),
             InlineButton("חזרה", f"{RETURN_BUTTON}{DELIMITER}{YEAR_PREFIX}")]
        )
        return InlineKeyboardMarkup(reply_keyboard)


def _send_day_choices(year, month):
    try:
        locale.setlocale(locale.LC_ALL, 'he_IL.utf8')
    finally:
        headers = [InlineButton(day_of_week.replace("'", ""), " ") for day_of_week in calendar.day_abbr]
        headers.insert(0, headers.pop())
        reply_keyboard = [headers[::-1]]
        calendar.setfirstweekday(calendar.SUNDAY)
        for week in calendar.monthcalendar(year=year, month=month):
            temp = []
            for day in week:
                if day == 0:
                    temp.append(InlineButton(" ", " "))
                else:
                    temp.append(InlineButton(str(day), f"{DAY_PREFIX}{DELIMITER}{day}"))
            reply_keyboard.append(temp[::-1])
        reply_keyboard.append(
            [InlineButton("ביטול", CANCEL_BUTTON),
             InlineButton("חזרה", f"{RETURN_BUTTON}{DELIMITER}{MONTH_PREFIX}")]
        )
        return InlineKeyboardMarkup(reply_keyboard)


def _process_calendar_step(bot):
    current_date_data = bot.context.get(f"{bot.PICKED_DATE_CONTEXT_PREFIX}{bot.message_id}", {})
    reply_keyboard = None
    if RETURN_BUTTON in bot.callback_query_data:
        return_to = bot.callback_query_data.split(DELIMITER)[-1]
        if return_to == YEAR_PREFIX:
            del current_date_data[YEAR_PREFIX]
            reply_keyboard = _send_year_choices()
        elif return_to == MONTH_PREFIX:
            del current_date_data[MONTH_PREFIX]
            reply_keyboard = _send_month_choices()

    elif YEAR_PREFIX in bot.callback_query_data:
        chosen_year = bot.callback_query_data.split(DELIMITER)[-1]
        current_date_data[YEAR_PREFIX] = chosen_year
        reply_keyboard = _send_month_choices()
    elif MONTH_PREFIX in bot.callback_query_data:
        chosen_month = bot.callback_query_data.split(DELIMITER)[-1]
        current_date_data[MONTH_PREFIX] = chosen_month
        reply_keyboard = _send_day_choices(year=int(current_date_data[YEAR_PREFIX]), month=int(chosen_month))
    elif DAY_PREFIX in bot.callback_query_data:
        chosen_day = bot.callback_query_data.split(DELIMITER)[-1]
        current_date_data[DAY_PREFIX] = chosen_day
        bot.edit_inline_message(
            f"{current_date_data[DAY_PREFIX]}/{current_date_data[MONTH_PREFIX]}/{current_date_data[YEAR_PREFIX]}בחרת בתאריך: ")
        bot.finished_picking_date = True
    elif CANCEL_BUTTON in bot.callback_query_data:
        chosen_date_data = {}
        bot.update_context({f"{bot.IS_DATE_PICKING_CONTEXT_PREFIX}{bot.message_id}": False})
        # TODO: think about this...
        bot.edit_inline_message("בחירת תאריך בוטלה")
    else:
        # TODO: think about this?
        pass

    bot.update_context({
        f"{bot.PICKED_DATE_CONTEXT_PREFIX}{bot.message_id}": current_date_data
    })
    if reply_keyboard:
        bot.edit_inline_message(rmarkup=reply_keyboard)
