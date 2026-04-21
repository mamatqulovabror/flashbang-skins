import asyncio
import os
import json
import hashlib
import hmac
import time
import re
import requests
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from database import create_db, save_user, get_stats, add_listing, get_listings, mark_listing_sold, get_all_users

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://flashbang-skins-production.up.railway.app")
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "457E07EF6DF40BDC7E08363AB347D9F5")
ADMIN_ID = 746409702

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def get_steam_login_url(return_url):
    from urllib.parse import urlencode
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_url,
        "openid.realm": WEBAPP_URL,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return STEAM_OPENID_URL + "?" + urlencode(params)

def verify_steam_openid(params):
    check_params = dict(params)
    check_params["openid.mode"] = "check_authentication"
    try:
        r = requests.post(STEAM_OPENID_URL, data=check_params, timeout=10)
        return "is_valid:true" in r.text
    except:
        return False

def extract_steam_id(claimed_id):
    match = re.search(r'(\d{17})$', claimed_id)
    return match.group(1) if match else None

def get_steam_profile(steam_id):
    try:
        url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={steam_id}"
        r = requests.get(url, timeout=10)
        data = r.json()
        players = data.get("response", {}).get("players", [])
        return players[0] if players else {}
    except:
        return {}

def get_steam_inventory(steam_id):
    try:
        url = f"https://steamcommunity.com/inventory/{steam_id}/730/2?l=english&count=100"
        r = requests.get(url, timeout=15)
        data = r.json()
        if not data or not data.get("assets"):
            return []
        assets = {a["assetid"]: a for a in data.get("assets", [])}
        descriptions = {f"{d['classid']}_{d['instanceid']}": d for d in data.get("descriptions", [])}
        items = []
        for asset_id, asset in assets.items():
            key = f"{asset['classid']}_{asset['instanceid']}"
            desc = descriptions.get(key, {})
            if not desc.get("tradable", 0):
                continue
            name = desc.get("market_hash_name", desc.get("name", "Unknown"))
            icon = desc.get("icon_url", "")
            image_url = f"https://steamcommunity-a.akamaihd.net/economy/image/{icon}/256fx256f" if icon else ""
            tags = desc.get("tags", [])
            wear = ""
            for tag in tags:
                if tag.get("category") == "Exterior":
                    wear = tag.get("localized_tag_name", "")
                    break
            items.append({"assetid": asset_id, "name": name, "image": image_url, "wear": wear})
        return items[:50]
    except Exception as e:
        print(f"Inventory error: {e}")
        return []

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo'q.")
        return
    total, online = get_stats()
    users = get_all_users()
    import datetime
    text = f"👑 *ADMIN PANEL*\n\n"
    text += f"📊 Jami: *{total}*\n"
    text += f"🟢 Online: *{online}*\n\n"
    text += f"👥 *So'nggi 20:*\n"
    for u in users[:20]:
        uid, uname, first_seen, last_seen = u
        uname_str = f"@{uname}" if uname else f"ID:{uid}"
        last = datetime.datetime.fromtimestamp(last_seen).strftime("%d.%m %H:%M")
        is_online = "🟢" if (int(time.time()) - last_seen) < 300 else "⚫"
        text += f"{is_online} {uname_str} | {last}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("start"))
async def start(message: Message):
    save_user(message.from_user.id, message.from_user.username or "")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛒 Bozorga kirish", web_app=WebAppInfo(url=WEBAPP_URL + "?v=3"))
    ]])
    await message.answer(
        "🔫 FB SKINS | Flashbang\n\n👇 To'liq ekranda ochish:\nt.me/fbskinsbot/fbskins",
        reply_markup=keyboard
    )

async def handle_index(request):
    import pathlib
    index_path = pathlib.Path(__file__).parent / "webapp" / "index.html"
    return web.FileResponse(index_path)

async def handle_stats(request):
    total, online = get_stats()
    return web.Response(
        text=json.dumps({"total": total, "online": online}),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_steam_login(request):
    return_url = WEBAPP_URL + "/steam/callback"
    login_url = get_steam_login_url(return_url)
    raise web.HTTPFound(login_url)

async def handle_steam_callback(request):
    params = dict(request.query)
    claimed_id = params.get("openid.claimed_id", "")
    steam_id = extract_steam_id(claimed_id)
    if not steam_id or not verify_steam_openid(params):
        raise web.HTTPFound(WEBAPP_URL + "?login=failed")
    profile = get_steam_profile(steam_id)
    username = profile.get("personaname", "Unknown")
    avatar = profile.get("avatarmedium", "")
    raise web.HTTPFound(f"{WEBAPP_URL}?steam_id={steam_id}&username={username}&avatar={avatar}")

async def handle_inventory(request):
    steam_id = request.query.get("steam_id", "")
    if not steam_id:
        return web.Response(text=json.dumps({"error": "steam_id required"}),
            content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})
    items = get_steam_inventory(steam_id)
    return web.Response(text=json.dumps({"items": items}),
        content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})

async def handle_add_listing(request):
    try:
        data = await request.json()
        steam_id = data.get("steam_id")
        username = data.get("username")
        trade_url = data.get("trade_url")
        asset_id = data.get("asset_id")
        market_name = data.get("market_name")
        price = data.get("price")
        image_url = data.get("image_url", "")
        float_val = data.get("float_val", "")
        wear = data.get("wear", "")
        if not all([steam_id, trade_url, asset_id, market_name, price]):
            return web.Response(text=json.dumps({"error": "Missing fields"}),
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}, status=400)
        add_listing(steam_id, username, trade_url, asset_id, market_name, float(price), image_url, float_val, wear)
        return web.Response(text=json.dumps({"success": True}),
            content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        return web.Response(text=json.dumps({"error": str(e)}),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}, status=500)

async def handle_get_listings(request):
    rows = get_listings()
    listings = []
    for row in rows:
        listings.append({"id": row[0], "steam_id": row[1], "username": row[2],
            "asset_id": row[4], "market_name": row[5], "price": row[6],
            "image_url": row[7], "float_val": row[8], "wear": row[9], "status": row[10]})
    return web.Response(text=json.dumps({"listings": listings}),
        content_type="application/json", headers={"Access-Control-Allow-Origin": "*"})

async def handle_options(request):
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    })

async def start_polling_with_retry():
    await asyncio.sleep(2)
    while True:
        try:
            print("Bot polling started...")
            await dp.start_polling(bot, allowed_updates=["message"])
        except Exception as e:
            print(f"Polling error: {e}, retry in 5s...")
            await asyncio.sleep(5)

async def main():
    create_db()
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/steam/login", handle_steam_login)
    app.router.add_get("/steam/callback", handle_steam_callback)
    app.router.add_get("/api/inventory", handle_inventory)
    app.router.add_get("/api/listings", handle_get_listings)
    app.router.add_post("/api/listings", handle_add_listing)
    app.router.add_options("/api/listings", handle_options)
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Server started on port {port}")
    asyncio.create_task(start_polling_with_retry())
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
