import os
import json
import random
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# ENVIRONMENT
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# =========================
# FILE PATHS
# =========================
DATA_DIR = "data"
PLAYER_FILE = os.path.join(DATA_DIR, "players.json")
MARKET_FILE = os.path.join(DATA_DIR, "market.json")
TOURNAMENT_FILE = os.path.join(DATA_DIR, "tournament.json")

os.makedirs(DATA_DIR, exist_ok=True)


# =========================
# JSON HELPERS
# =========================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# =========================
# IN-MEMORY STATE
# =========================
players = load_json(PLAYER_FILE, {})
market = load_json(MARKET_FILE, [])
tournament = load_json(TOURNAMENT_FILE, {"players": []})


# =========================
# PLAYER MODEL
# =========================
def ensure_player(user):
    uid = str(user.id)
    if uid not in players:
        players[uid] = {
            "username": user.username or user.first_name,
            "tokens": 0,
            "chests": 0,
            "items": [],  # list of {id, name, slot, rarity, power}
            "equipped": {  # slot -> item_id or None
                "head": None,
                "body": None,
                "weapon": None,
                "legs": None,
                "trinket": None,
            },
            "referrer": None,
        }
    else:
        # keep username fresh
        players[uid]["username"] = user.username or user.first_name


def get_power(uid: str) -> int:
    p = players[uid]
    power = 0
    equipped_ids = set(p["equipped"].values()) - {None}
    for item in p["items"]:
        if item["id"] in equipped_ids:
            power += item.get("power", 0)
    return power


# =========================
# ITEM & CHEST LOGIC
# =========================

# slot: types of gear
SLOTS = ["head", "body", "weapon", "legs", "trinket"]

# RPG-lite item pool
ITEM_POOL = {
    "Common": [
        ("Rusty Visor", "head", 1),
        ("Worn Jacket", "body", 1),
        ("Cracked Blade", "weapon", 1),
        ("Street Boots", "legs", 1),
        ("Lucky Token", "trinket", 1),
    ],
    "Uncommon": [
        ("Neon Visor", "head", 3),
        ("Reinforced Coat", "body", 3),
        ("Pulse Saber", "weapon", 3),
        ("Sprint Greaves", "legs", 3),
        ("Circuit Charm", "trinket", 3),
    ],
    "Rare": [
        ("Ghost Crown", "head", 6),
        ("Aegis Harness", "body", 6),
        ("Quantum Edge", "weapon", 6),
        ("Phasewalkers", "legs", 6),
        ("Singularity Core", "trinket", 6),
    ],
}

RARITY_WEIGHTS = [("Common", 70), ("Uncommon", 23), ("Rare", 7)]


def new_item_id(uid: str) -> int:
    """Create a simple incremental item id per player."""
    p = players[uid]
    existing = [i["id"] for i in p["items"]]
    return (max(existing) + 1) if existing else 1


def roll_chest():
    rarity = random.choices(
        [r[0] for r in RARITY_WEIGHTS],
        [r[1] for r in RARITY_WEIGHTS],
    )[0]
    name, slot, power = random.choice(ITEM_POOL[rarity])
    tokens = random.randint(10, 30)
    return rarity, name, slot, power, tokens


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        "🔥 Welcome to *Fast Cash Tournament RPG*!\n\n"
        "🎱 *$5 Buy-In*  |  🏆 *Winner gets $15* (you handle payouts via Cash App).\n\n"
        "Each full table:\n"
        "• All 5 players get 1 loot chest\n"
        "• Winner gets +1 extra chest\n\n"
        "Loot gives cyberpunk gear (head/body/weapon/legs/trinket), each with power.\n"
        "Equip your best set, trade on the market, and flex your build.\n\n"
        "Use /join to enter the next table."
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = user.id

    if uid in tournament["players"]:
        return await update.message.reply_text("You are already in the current table.")

    tournament["players"].append(uid)
    save_json(TOURNAMENT_FILE, tournament)

    count = len(tournament["players"])
    await update.message.reply_text(
        f"🎮 {user.first_name} joined the *Fast Cash Table*.\n"
        f"Players: {count}/5"
    )

    if count == 5:
        # Table is ready
        await update.message.reply_text(
            "🔥 Table is FULL (5/5)!\n"
            "Admin: choose the winner with:\n"
            "/winner @username"
        )


async def winner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return await update.message.reply_text("You are not authorized to set winners.")

    if not tournament["players"]:
        return await update.message.reply_text("No active table.")

    if not context.args:
        return await update.message.reply_text("Usage: /winner @username")

    target_username = context.args[0].replace("@", "")
    winner_id = None

    # find winner by stored username
    for uid in tournament["players"]:
        uid_str = str(uid)
        if players.get(uid_str, {}).get("username") == target_username:
            winner_id = uid
            break

    if winner_id is None:
        return await update.message.reply_text("That user is not in the table.")

    # Everyone gets 1 chest, winner gets +1
    for uid in tournament["players"]:
        ensure_player(update.effective_user)  # just to be safe
        players[str(uid)]["chests"] += 1
    players[str(winner_id)]["chests"] += 1

    save_json(PLAYER_FILE, players)

    # Reset table
    tournament["players"] = []
    save_json(TOURNAMENT_FILE, tournament)

    await update.message.reply_text(
        f"🏆 Winner: @{players[str(winner_id)]['username']}\n"
        f"💵 Payout: *$15* (you send manually via Cash App).\n"
        "📦 All players got 1 loot chest, winner got 2 total!\n\n"
        "Players can now use /open_chest to open their loot."
    )


async def open_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if p["chests"] <= 0:
        return await update.message.reply_text("You have no chests to open.")

    p["chests"] -= 1
    rarity, name, slot, power, tokens = roll_chest()

    item = {
        "id": new_item_id(uid),
        "name": name,
        "slot": slot,
        "rarity": rarity,
        "power": power,
    }
    p["items"].append(item)
    p["tokens"] += tokens

    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        "📦 *Chest opened!*\n"
        f"🎁 Item: *{name}* ({rarity}, slot: {slot}, +{power} power)\n"
        f"💠 Tokens gained: {tokens}\n\n"
        "Use /inventory to view all items, /equip to wear your best gear."
    )


async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if not p["items"]:
        item_text = "No gear yet. Win tournaments and open chests!"
    else:
        lines = []
        for idx, item in enumerate(p["items"], start=1):
            lines.append(
                f"{idx}. {item['name']} "
                f"({item['rarity']}, slot: {item['slot']}, power {item['power']})"
            )
        item_text = "\n".join(lines)

    chest_text = f"Chests: {p['chests']}"
    token_text = f"Tokens: {p['tokens']}"
    power_text = f"Total Power (equipped): {get_power(uid)}"

    await update.message.reply_text(
        f"🎒 *Inventory for {p['username']}*\n\n"
        f"{chest_text}\n"
        f"{token_text}\n"
        f"{power_text}\n\n"
        f"*Items:*\n{item_text}"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    eq = p["equipped"]
    equipped_lines = []
    for slot in SLOTS:
        item_id = eq.get(slot)
        if item_id is None:
            equipped_lines.append(f"{slot.capitalize()}: (empty)")
        else:
            item = next((i for i in p["items"] if i["id"] == item_id), None)
            if item:
                equipped_lines.append(
                    f"{slot.capitalize()}: {item['name']} "
                    f"({item['rarity']}, +{item['power']} power)"
                )
            else:
                equipped_lines.append(f"{slot.capitalize()}: (missing)")

    equip_text = "\n".join(equipped_lines)
    power_total = get_power(uid)

    await update.message.reply_text(
        f"🧬 *Build for {p['username']}*\n\n"
        f"{equip_text}\n\n"
        f"Total Power: *{power_total}*"
    )


async def equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if not context.args:
        return await update.message.reply_text("Usage: /equip <item_number> (from /inventory)")

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        return await update.message.reply_text("Item number must be a number.")

    if idx < 0 or idx >= len(p["items"]):
        return await update.message.reply_text("Invalid item number.")

    item = p["items"][idx]
    slot = item["slot"]

    p["equipped"][slot] = item["id"]
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        f"✅ Equipped *{item['name']}* to {slot} slot.\n"
        "Use /stats to view your full build."
    )


async def unequip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if not context.args:
        return await update.message.reply_text("Usage: /unequip <slot>")

    slot = context.args[0].lower()
    if slot not in SLOTS:
        return await update.message.reply_text(
            f"Invalid slot. Choose from: {', '.join(SLOTS)}"
        )

    if p["equipped"].get(slot) is None:
        return await update.message.reply_text(f"No item equipped in {slot}.")

    p["equipped"][slot] = None
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(f"🧷 Unequipped item from {slot} slot.")


# =========================
# MARKETPLACE
# =========================

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not market:
        return await update.message.reply_text("🛒 Marketplace is empty.")

    lines = []
    for i, listing in enumerate(market, start=1):
        item = listing["item"]
        seller = players.get(str(listing["seller_id"]), {}).get("username", "Unknown")
        lines.append(
            f"{i}. {item['name']} ({item['rarity']}, slot {item['slot']}, power {item['power']}) "
            f"- {listing['price']} tokens (seller: @{seller})"
        )

    await update.message.reply_text("*🛒 Marketplace Listings:*\n\n" + "\n".join(lines))


async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /sell <item_number> <price>")

    try:
        idx = int(context.args[0]) - 1
        price = int(context.args[1])
    except ValueError:
        return await update.message.reply_text("Item number and price must be numbers.")

    if idx < 0 or idx >= len(p["items"]):
        return await update.message.reply_text("Invalid item number.")

    item = p["items"].pop(idx)

    listing = {
        "seller_id": user.id,
        "item": item,
        "price": price,
    }

    market.append(listing)
    save_json(MARKET_FILE, market)
    save_json(PLAYER_FILE, players)

    await update.message.reply_text("📦 Item listed on the marketplace.")


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)
    p = players[uid]

    if not context.args:
        return await update.message.reply_text("Usage: /buy <listing_number>")

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        return await update.message.reply_text("Listing number must be a number.")

    if idx < 0 or idx >= len(market):
        return await update.message.reply_text("Invalid listing.")

    listing = market[idx]
    price = listing["price"]

    if p["tokens"] < price:
        return await update.message.reply_text("You don't have enough tokens.")

    item = listing["item"]
    rarity = item["rarity"]

    # fee model (you keep the fee)
    fee_map = {"Common": 0.02, "Uncommon": 0.04, "Rare": 0.06}
    fee_rate = fee_map.get(rarity, 0.02)
    fee = int(price * fee_rate)
    seller_take = price - fee

    # transfer tokens
    p["tokens"] -= price
    seller_id = str(listing["seller_id"])
    ensure_player(update.effective_user)  # ensure structure exists
    if seller_id in players:
        players[seller_id]["tokens"] += seller_take

    # give item to buyer
    p["items"].append(item)

    # remove from market
    market.pop(idx)

    save_json(MARKET_FILE, market)
    save_json(PLAYER_FILE, players)

    await update.message.reply_text(
        f"✅ Bought *{item['name']}* for {price} tokens.\n"
        f"🧾 Fee: {fee} tokens | Seller received: {seller_take} tokens."
    )


# =========================
# SIMPLE REFERRAL (MVP)
# =========================

async def promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_player(user)
    uid = str(user.id)

    code = uid  # simple: user id is referral code
    text = (
        "📣 *Fast Cash Referral Program*\n\n"
        "Share this referral code or link with new players.\n"
        "When they join and you verify them, you pay them $2 via Cash App.\n\n"
        f"Referral code: `{code}`\n"
        "You can manually track who used your code for now – we’ll automate later."
    )
    await update.message.reply_text(text)


# =========================
# ADMIN / DEBUG
# =========================

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <message>")

    msg = " ".join(context.args)
    for uid in players.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 {msg}")
        except Exception:
            continue

    await update.message.reply_text("Broadcast sent.")


# =========================
# MAIN
# =========================

def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("winner", winner))
    application.add_handler(CommandHandler("open_chest", open_chest))
    application.add_handler(CommandHandler("inventory", inventory))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("equip", equip))
    application.add_handler(CommandHandler("unequip", unequip))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("sell", sell))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("promo", promo))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))

    application.run_polling()


if __name__ == "__main__":
    main()
