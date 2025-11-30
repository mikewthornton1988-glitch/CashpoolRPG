import logging
import json
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# -------------------------
# ENV VARIABLES
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# -------------------------
# DATA FILES
# -------------------------
DATA_DIR = "data"
PLAYER_FILE = f"{DATA_DIR}/players.json"
MARKET_FILE = f"{DATA_DIR}/market.json"
TOURNAMENT_FILE = f"{DATA_DIR}/tournament.json"

os.makedirs(DATA_DIR, exist_ok=True)

# -------------------------
# LOAD / SAVE HELPERS
# -------------------------
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# -------------------------
# DATA STORAGE
# -------------------------
players = load_json(PLAYER_FILE, {})
market = load_json(MARKET_FILE, [])
tournament = load_json(TOURNAMENT_FILE, {"players": []})

# -------------------------
# PLAYER INIT
# -------------------------
def ensure_player(user_id):
    if str(user_id) not in players:
        players[str(user_id)] = {
            "username": "",
            "tokens": 0,
            "chests": 0,
            "items": []
        }

# -------------------------
# CHEST OPENING LOGIC
# -------------------------
ITEM_POOL = {
    "Common": ["Rusted Blade", "Scratched Visor", "Basic Gloves", "Light Boots"],
    "Uncommon": ["Street Jacket", "Holo Badge", "Pulse Dagger"],
    "Rare": ["Neon Saber", "Ghost Core", "Cyber Crown"]
}

RARITY_WEIGHTS = [
    ("Common", 75),
    ("Uncommon", 20),
    ("Rare", 5)
]

def open_basic_chest():
    rarity = random.choices(
        [r[0] for r in RARITY_WEIGHTS],
        [r[1] for r in RARITY_WEIGHTS]
    )[0]
    item = random.choice(ITEM_POOL[rarity])
    tokens = random.randint(10, 25)
    return rarity, item, tokens

# -------------------------
# COMMAND: /start
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user.id)

    players[str(user.id)]["username"] = user.username or user.first_name
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        "🔥 Welcome to *Fast Cash Tournament*!\n\n"
        "💵 *$5 Buy-In*\n"
        "🏆 *Winner Gets $15*\n"
        "📦 Everyone gets a chest!\n"
        "📦 Winner gets *2 chests*\n\n"
        "Use /join to enter the next tournament!"
    )

# -------------------------
# COMMAND: /join
# -------------------------
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user.id)

    if user.id in tournament["players"]:
        await update.message.reply_text("You're already in the current tournament!")
        return

    tournament["players"].append(user.id)
    save_json(TOURNAMENT_FILE, tournament)

    await update.message.reply_text(
        f"🎮 {user.first_name} joined the *Fast Cash Tournament*!\n"
        f"Players: {len(tournament['players'])}/5"
    )

    if len(tournament["players"]) == 5:
        await update.message.reply_text(
            "🔥 Tournament is FULL!\n"
            "Admin must choose the winner:\n"
            "/winner @username"
        )

# -------------------------
# COMMAND: /winner (ADMIN)
# -------------------------
async def winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("You are not authorized.")

    if not tournament["players"]:
        return await update.message.reply_text("No tournament running.")

    if not context.args:
        return await update.message.reply_text("Usage: /winner @username")

    target_username = context.args[0].replace("@", "")
    winner_id = None

    for uid in tournament["players"]:
        if players[str(uid)]["username"] == target_username:
            winner_id = uid
            break

    if not winner_id:
        return await update.message.reply_text("User not found in tournament.")

    # Give chests
    for uid in tournament["players"]:
        ensure_player(uid)
        players[str(uid)]["chests"] += 1  # everyone
    players[str(winner_id)]["chests"] += 1  # +1 extra for winner

    save_json(PLAYER_FILE, players)

    # Announce
    await update.message.reply_text(
        f"🏆 Winner: @{players[str(winner_id)]['username']}\n"
        f"💵 They win *$15*!\n"
        f"📦 All players received a chest!"
    )

    # Reset tournament
    tournament["players"] = []
    save_json(TOURNAMENT_FILE, tournament)

# -------------------------
# COMMAND: /open_chest
# -------------------------
async def open_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user.id)

    if players[str(user.id)]["chests"] <= 0:
        return await update.message.reply_text("You have no chests!")

    players[str(user.id)]["chests"] -= 1

    rarity, item, tokens = open_basic_chest()

    players[str(user.id)]["items"].append({"rarity": rarity, "name": item})
    players[str(user.id)]["tokens"] += tokens

    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        f"📦 *Chest Opened!*\n"
        f"🎁 Item: *{item}* ({rarity})\n"
        f"💠 Tokens gained: {tokens}"
    )

# -------------------------
# COMMAND: /inventory
# -------------------------
async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user.id)

    p = players[str(user.id)]
    item_list = "\n".join([f"- {i['name']} ({i['rarity']})" for i in p["items"]]) or "No items."

    await update.message.reply_text(
        f"🎒 *Your Inventory*\n\n"
        f"Tokens: {p['tokens']}\n"
        f"Chests: {p['chests']}\n\n"
        f"*Items:*\n{item_list}"
    )

# -------------------------
# MARKETPLACE
# -------------------------
async def sell(update, context):
    user = update.effective_user
    ensure_player(user.id)

    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /sell <item_number> <price>")

    idx = int(context.args[0]) - 1
    price = int(context.args[1])

    p = players[str(user.id)]

    if idx < 0 or idx >= len(p["items"]):
        return await update.message.reply_text("Invalid item number.")

    item = p["items"].pop(idx)

    listing = {
        "seller_id": user.id,
        "item": item,
        "price": price
    }

    market.append(listing)
    save_json(MARKET_FILE, market)
    save_json(PLAYER_FILE, players)

    await update.message.reply_text("📦 Item listed on marketplace!")

async def market_cmd(update, context):
    if not market:
        return await update.message.reply_text("Marketplace empty.")

    text = "*🛒 Marketplace Listings:*\n\n"
    for i, listing in enumerate(market, start=1):
        item = listing["item"]
        text += f"{i}. {item['name']} ({item['rarity']}) – {listing['price']} tokens\n"

    await update.message.reply_text(text)

async def buy(update, context):
    user = update.effective_user
    ensure_player(user.id)

    if not context.args:
        return await update.message.reply_text("Usage: /buy <listing_number>")

    idx = int(context.args[0]) - 1

    if idx < 0 or idx >= len(market):
        return await update.message.reply_text("Invalid listing.")

    listing = market[idx]
    price = listing["price"]

    # Check tokens
    if players[str(user.id)]["tokens"] < price:
        return await update.message.reply_text("Not enough tokens.")

    # Apply fee model B
    rarity = listing["item"]["rarity"]
    fee_map = {"Common": 0.02, "Uncommon": 0.04, "Rare": 0.06}
    fee = int(price * fee_map.get(rarity, 0.02))

    seller_take = price - fee

    # Deduct tokens
    players[str(user.id)]["tokens"] -= price
    players[str(listing["seller_id"])]["tokens"] += seller_take

    # Give item
    players[str(user.id)]["items"].append(listing["item"])

    # Remove from market
    market.pop(idx)

    save_json(MARKET_FILE, market)
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        f"✅ Bought *{listing['item']['name']}* for {price} tokens.\n"
        f"🧾 Fee: {fee} tokens\n"
        f"Seller received: {seller_take} tokens"
    )

# -------------------------
# MAIN
# -------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("winner", winner))
    app.add_handler(CommandHandler("open_chest", open_chest))
    app.add.add_handler(CommandHandler("inventory", inventory))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("market", market_cmd))
    app.add_handler(CommandHandler("buy", buy))

    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
