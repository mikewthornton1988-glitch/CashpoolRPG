import json
import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

DATA_DIR = "data"
PLAYERS_FILE = os.path.join(DATA_DIR, "players.json")
MARKET_FILE = os.path.join(DATA_DIR, "market.json")
TOURN_FILE = os.path.join(DATA_DIR, "tournament.json")

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ------------------------------
# Data Helpers
# ------------------------------
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


# ------------------------------
# Commands
# ------------------------------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to CashPool RPG.\nUse /join, /play, /leaderboard")


async def join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    players = load_json(PLAYERS_FILE, {})
    uid = str(update.effective_user.id)

    if uid not in players:
        players[uid] = {
            "name": update.effective_user.first_name,
            "wins": 0,
            "losses": 0,
            "credits": 0
        }
        save_json(PLAYERS_FILE, players)
        await update.message.reply_text("You have joined the game!")
    else:
        await update.message.reply_text("You are already registered.")


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tourn = load_json(TOURN_FILE, {"tournaments": []})

    if not tourn["tournaments"]:
        await update.message.reply_text("No tournaments available right now.")
        return

    t = tourn["tournaments"][0]  # only 1 for now

    label = f"{t['name']} – ${t['buy_in']} buy-in"
    await update.message.reply_text(f"Tournament available:\n{label}\nUse /join to enter.")


async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    players = load_json(PLAYERS_FILE, {})

    if not players:
        await update.message.reply_text("No players yet.")
        return

    sorted_players = sorted(players.values(), key=lambda x: x["wins"], reverse=True)

    text = "🏆 Leaderboard 🏆\n"
    for p in sorted_players[:10]:
        text += f"{p['name']}: {p['wins']} wins\n"

    await update.message.reply_text(text)


# ------------------------------
# Main Bot Setup
# ------------------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    print("Bot is running...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
