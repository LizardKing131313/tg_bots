import asyncio

from aiogram import Bot, Dispatcher

from libs.common.aiogram.error_handler import setup_error_handlers
from libs.common.aiogram.i18n import create_i18n
from libs.common.config import get_settings
from libs.common.logger import setup_logging
from libs.common.middleware.keyboard_cleanup_middleware import keyboard_cleanup_middleware
from libs.common.middleware.rate_limit_middleware import rate_limit_middleware

from .handlers import questionnaire


BOT_NAME = "questionnaire_bot"


def on_startup() -> None:
    log = setup_logging(BOT_NAME)
    log.info("Questionnaire bot started.")


async def start_bot() -> None:
    bot = Bot(token=get_settings(bot_name=BOT_NAME).bot_token)
    dp = Dispatcher()

    dp.update.middleware(create_i18n(bot_name=BOT_NAME))
    dp.update.middleware(rate_limit_middleware(bot_name=BOT_NAME))
    dp.message.middleware(keyboard_cleanup_middleware(bot_name=BOT_NAME))
    dp.callback_query.middleware(keyboard_cleanup_middleware(bot_name=BOT_NAME))

    setup_error_handlers(bot_name=BOT_NAME, dp=dp)

    questionnaire.register(dp)

    dp.startup.register(on_startup)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def run() -> int:
    try:
        asyncio.run(start_bot())
        return 0
    except (KeyboardInterrupt, SystemExit):
        return 0
