import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from libs.common.aiogram.error_handler import setup_error_handlers
from libs.common.aiogram.i18n import _, create_i18n
from libs.common.config import get_settings
from libs.common.logger import setup_logging
from libs.common.middleware.rate_limit_middleware import rate_limit_middleware


BOT_NAME = "echo_bot"


def on_startup() -> None:
    log = setup_logging(BOT_NAME)
    log.info("Echo bot started.")


async def start_bot() -> None:
    bot = Bot(token=get_settings(bot_name=BOT_NAME).bot_token)
    dp = Dispatcher()

    dp.update.middleware(create_i18n(bot_name=BOT_NAME))
    dp.update.middleware(rate_limit_middleware(bot_name=BOT_NAME))

    setup_error_handlers(bot_name=BOT_NAME, dp=dp)

    @dp.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        await message.answer(_("label.echo.greeting"))

    @dp.message(F.text)
    async def echo_text(message: Message) -> None:
        await message.answer(message.text)

    dp.startup.register(on_startup)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def run() -> int:
    try:
        asyncio.run(start_bot())
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 0
