# telegram bot service
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, MenuButtonWebApp

from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def start_handler(message: types.Message) -> None:
    """handle start command"""
    await message.answer(
        "Open Wished from the menu button below."
    )


async def main() -> None:
    """start telegram bot polling"""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.error("telegram bot token not set")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.register(start_handler, CommandStart())

    web_app_url = settings.telegram_mini_app_url or "http://localhost:3000"
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Open Wished",
            web_app=WebAppInfo(url=web_app_url),
        )
    )

    logger.info("starting telegram bot polling")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
