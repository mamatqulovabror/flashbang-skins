import asyncio, os, json, hashlib, hmac, time, re
import requests
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from database import create_db, save_user, get_stats, add_listing, get_listings, mark_listing_sold

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://flashbang-skins-production.up.railway.app")
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "457E07EF6DF40BDC7E08363AB347D9F5")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---- STEAM OPENID ----
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def get_steam_login_url(return_url):
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_url,
        "openid.realm": WEBAPP_URL,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    from urllib.parse import urlencode
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
            
            items.append({
                "assetid": asset_id,
                "name": name,
                "image": image_url,
                "wear": wear,
            })
        
        return items[:50]
    except Exception as e:
        print(f"Inventory error: {e}")
        return []

def get_trade_url(steam_id):
    try:
        url = f"https://api.steampowered.com/IEconService/GetTradeOffersSummary/v1/?key={STEAM_API_KEY}&time_last_visit=0"
        return None
    except:
        return None

# ---- TELEGRAM BOT ----
@dp.message(Command("start"))
async def start(message: Message):
    save_user(message.from_user.id, message.from_user.username or "")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛒 Bozorga kirish", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])
    await message.answer(
        "🔫 FB SKINS | Flashbang\n\n"
        "👇 To'liq ekranda ochish:\n"
        "t.me/fbskinsbot/fbskins",
        reply_markup=keyboard
    )

# ---- WEB HANDLERS ----
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
    """Steam OpenID login redirect"""
    return_url = WEBAPP_URL + "/steam/callback"
    login_url = get_steam_login_url(return_url)
    raise web.HTTPFound(login_url)

async def handle_steam_callback(request):
    """Steam OpenID callback"""
    params = dict(request.query)
    claimed_id = params.get("openid.claimed_id", "")
    steam_id = extract_steam_id(claimed_id)
    
    if not steam_id or not verify_steam_openid(params):
        raise web.HTTPFound(WEBAPP_URL + "?login=failed")
    
    profile = get_steam_profile(steam_id)
    username = profile.get("personaname", "Unknown")
    avatar = profile.get("avatarmedium", "")
    
    redirect_url = f"{WEBAPP_URL}?steam_id={steam_id}&username={username}&avatar={avatar}"
    raise web.HTTPFound(redirect_url)

async def handle_inventory(request):
    """Foydalanuvchi inventarini olish"""
    steam_id = request.query.get("steam_id", "")
    if not steam_id:
        return web.Response(
            text=json.dumps({"error": "steam_id required"}),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    items = get_steam_inventory(steam_id)
    return web.Response(
        text=json.dumps({"items": items}),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_add_listing(request):
    """Skin sotuvga qo'yish"""
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
            return web.Response(
                text=json.dumps({"error": "Missing required fields"}),
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
                status=400
            )
        
        add_listing(steam_id, username, trade_url, asset_id, market_name, float(price), image_url, float_val, wear)
        return web.Response(
            text=json.dumps({"success": True}),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        return web.Response(
            text=json.dumps({"error": str(e)}),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
            status=500
        )

async def handle_get_listings(request):
    """Barcha aktiv listinglarni olish"""
    rows = get_listings()
    listings = []
    for row in rows:
        listings.append({
            "id": row[0],
            "steam_id": row[1],
            "username": row[2],
            "asset_id": row[4],
            "market_name": row[5],
            "price": row[6],
            "image_url": row[7],
            "float_val": row[8],
            "wear": row[9],
            "status": row[10],
        })
    return web.Response(
        text=json.dumps({"listings": listings}),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_options(request):
    return web.Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
