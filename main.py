import json
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# -------------------
# Load environment
# -------------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

# -------------------
# File paths
# -------------------
DATA_DIR = Path(__file__).parent / "data"
PLAYERS_FILE = DATA_DIR / "players.json"
MARKET_FILE = DATA_DIR / "market.json"
TOURNAMENT_FILE = DATA_DIR / "tournament.json"

# -------------------
# Utility functions
# -------------------
def load_json(file_path, default):
    if not file_path.exists():
        file_path.write_text(json.dumps(default, indent=2))
        return default
    try:
        return json.loads(file_path.read_text())
    except:
        return default

def save_json(file_path, data):
    file_path.write_text(json.dumps(data, indent=2))

# -------------------
# Player initialization
# -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    players = load_json(PLAYERS_FILE, {})

    if str(user.id) not in players:
        players[str(user.id)] = {
            "name": user.first_name,
            "coins": 0,
            "chests": 0,
            "inventory": []
        }
        save_json(PLAYERS_FILE, players)

    await update.message.reply_text(
        "Welcome to CashPool RPG!\n"
        "You earn rewards, open chests, trade items, and join pool tournaments.\n\n"
        "Commands:\n"
        "/chest — open a chest\n"
        "/coins — check your coins\n"
        "/join — join tournament queue\n"
        "/market — view marketplace"
    )

# -------------------
# Show coins
# -------------------
async def coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})

    bal = players.get(user_id, {}).get("coins", 0)
    await update.message.reply_text(f"You have {bal} coins.")

# -------------------
# Open chest
# -------------------
async def chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    players = load_json(PLAYERS_FILE, {})

    if players[user_id]["chests"] <= 0:
        await update.message.reply_text("You don’t have any chests!")
        return

    players[user_id]["chests"] -= 1
    players[user_id]["coins"] += 5  # simple drop for now
    save_json(PLAYERS_FILE, players)

    await update.message.reply_text(
        "You opened a chest and found 5 coins!"
    )

# -------------------
# Tournament join
# -------------------
async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tournament = load_json(TOURNAMENT_FILE, {"queue": []})

    if user.id in tournament["queue"]:
        await update.message.reply_text("You're already in the queue.")
        return

    tournament["queue"].append(user.id)
    save_json(TOURNAMENT_FILE, tournament)

    await update.message.reply_text(
        f"You joined the tournament queue. "
        f"Players joined: {len(tournament['queue'])}/5"
    )

# -------------------
# View marketplace
# -------------------
async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    market = load_json(MARKET_FILE, {})
    if not market:
        await update.message.reply_text("Marketplace is empty for now.")
        return

    msg = "Marketplace Listings:\n"
    for item_id, item in market.items():
        msg += f"- {item['name']} — {item['price']} coins\n"

    await update.message.reply_text(msg)

# -------------------
# Start bot
# -------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("coins", coins))
    app.add_handler(CommandHandler("chest", chest))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("market", market))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
