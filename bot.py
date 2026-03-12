import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://flashbang-skins-production.up.railway.app")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBAPP_URL}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛒 Bozorga kirish", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer("🔫 FB SKINS | Flashbang", reply_markup=keyboard)

async def handle_index(request):
    import pathlib
    index_path = pathlib.Path(__file__).parent / "webapp" / "index.html"
    return web.FileResponse(index_path)

async def handle_webhook(request):
    from aiogram.types import Update
    import json
    data = await request.json()
    update = Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

async def on_startup(app):
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook set: {WEBHOOK_URL}")

async def on_shutdown(app):
    await bot.delete_webhook()

async def main():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Started on port {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
