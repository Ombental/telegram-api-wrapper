from dataclasses import dataclass, field


@dataclass
class InlineButton:
    text: str = field(init=True)
    callback_data: str | int = field(init=True)
