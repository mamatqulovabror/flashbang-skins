import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from database import create_db

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://telegram.org")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🛒 Bozorga kirish",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]])
    await message.answer("🔫 FB SKINS | Flashbang", reply_markup=keyboard)

async def main():
    create_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
