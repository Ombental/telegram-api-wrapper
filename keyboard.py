import datetime
import json
from typing import Set


# mostly taken from - https://github.com/python-telegram-bot/python-telegram-bot/blob/master/telegram/_telegramobject.py

class ReplyKeyboardMarkup:
    __slots__ = (
        "keyboard",
        "one_time_keyboard",
    )

    def __init__(self, keyboard, one_time_keyboard: bool = False):
        self.keyboard = tuple(
            tuple({"text": button} if isinstance(button, str) else button for button in row)
            for row in keyboard
        )
        self.one_time_keyboard = one_time_keyboard

    def _get_attrs(self):
        data = {}

        for key in self.__slots__:
            value = getattr(self, key, None)
            data[key] = value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self, recursive: bool = True):
        out = self._get_attrs()

        # Now we should convert TGObjects to dicts inside objects such as sequences, and convert
        # datetimes to timestamps. This mostly eliminates the need for subclasses to override
        # `to_dict`
        pop_keys: Set[str] = set()
        for key, value in out.items():
            if isinstance(value, (tuple, list)):
                if not value:
                    # not popping directly to avoid changing the dict size during iteration
                    pop_keys.add(key)
                    continue

                val = []  # empty list to append our converted values to
                for item in value:
                    if hasattr(item, "to_dict"):
                        val.append(item.to_dict(recursive=recursive))
                    # This branch is useful for e.g. Tuple[Tuple[PhotoSize|KeyboardButton]]
                    elif isinstance(item, (tuple, list)):
                        val.append(
                            [
                                i.to_dict(recursive=recursive) if hasattr(i, "to_dict") else i
                                for i in item
                            ]
                        )
                    else:  # if it's not a TGObject, just append it. E.g. [TGObject, 2]
                        val.append(item)
                out[key] = val

            elif isinstance(value, datetime.datetime):
                out[key] = value.isoformat()

        for key in pop_keys:
            out.pop(key)

        # Effectively "unpack" api_kwargs into `out`:
        out.update(out.pop("api_kwargs", {}))  # type: ignore[call-overload]
        return out
