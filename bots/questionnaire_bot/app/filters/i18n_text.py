from aiogram.filters import BaseFilter
from aiogram.types import Message

from libs.common.aiogram.i18n import _


class I18nTextEquals(BaseFilter):
    def __init__(self, key: str) -> None:
        self.key = key

    async def __call__(self, message: Message) -> bool:
        expected = _(self.key).strip().casefold()
        actual = (message.text or "").strip().casefold()
        return actual == expected
