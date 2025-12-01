import os
import json
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------- CONFIG ----------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PLAYERS_FILE = DATA_DIR / "players.json"
MARKET_FILE = DATA_DIR / "market.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("cashpool_tournament_bot")


# ---------- JSON HELPERS ----------

def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if data is not None else default
    except Exception as e:
        logger.error(f"Error loading %s: %s", path, e)
        return default


def save_json(path: Path, data):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving %s: %s", path, e)


def default_market():
    return {
        "tournaments": [
            {
                "id": "5wta",
                "name": "$5 Winner Takes All",
                "buy_in": 5.0,
                "payout_type": "wta",
                "prize_pool_pct": 0.75,
            },
            {
                "id": "10wta",
                "name": "$10 Winner Takes All",
                "buy_in": 10.0,
                "payout_type": "wta",
                "prize_pool_pct": 0.75,
            },
            {
                "id": "10top2",
                "name": "$10 Top-2 Payout",
                "buy_in": 10.0,
                "payout_type": "top2",
                "prize_pool_pct": 0.75,
            },
            {
                "id": "20top3",
                "name": "$20 Top-3 Payout",
                "buy_in": 20.0,
                "payout_type": "top3",
                "prize_pool_pct": 0.75,
            },
        ],
        "entries": [],
    }


def get_players():
    data = load_json(PLAYERS_FILE, {})
    if not isinstance(data, dict):
        data = {}
    return data


def save_players(players):
    save_json(PLAYERS_FILE, players)


def get_market():
    data = load_json(MARKET_FILE, default_market())
    if "tournaments" not in data:
        data["tournaments"] = default_market()["tournaments"]
    if "entries" not in data:
        data["entries"] = []
    return data


def save_market(market):
    save_json(MARKET_FILE, market)


def find_tournament(t_id: str):
    market = get_market()
    for t in market["tournaments"]:
        if t["id"] == t_id:
            return t
    return None


# ---------- HANDLERS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    players = get_players()
    uid = str(user.id)

    if uid not in players:
        players[uid] = {
            "username": user.username or user.full_name,
            "joined_at": datetime.utcnow().isoformat(),
            "total_buyins": 0.0,
            "entries": 0,
        }
        save_players(players)

    text = (
        "🎱 Welcome to Cash Pool Tournaments!\n\n"
        "This bot logs entries and buy-ins for your real 8-ball cash tables.\n"
        "All real money still moves through you (Cash App, in person, etc.).\n\n"
        "Use the buttons below to view tournaments and join tables."
    )

    keyboard = [
        [InlineKeyboardButton("📜 View Tournaments", callback_data="menu_tournaments")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
    ]

    if update.message:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.effective_chat.send_message(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Commands:\n"
        "/start – open main menu\n"
        "/help – show this help\n\n"
        "Use the buttons to join tournaments. The bot just tracks entries and totals."
    )
    await update.message.reply_text(text)


async def tournaments_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    market = get_market()
    buttons = []
    for t in market["tournaments"]:
        label = f\"{t['name']} – ${t['buy_in']:.0f} buy-in\"
        buttons.append(
            [InlineKeyboardButton(label, callback_data=f\"join_{t['id']}\")]
        )

    if not buttons:
        await query.edit_message_text("No tournaments configured yet.")
        return

    buttons.append(
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
    )

    await query.edit_message_text(
        "🎱 Active Tournaments:\n"
        "Tap a tournament when a real-world table is forming.\n"
        "The bot logs entries; you handle the cash.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📜 View Tournaments", callback_data="menu_tournaments")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
    ]

    await query.edit_message_text(
        "Main menu:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    players = get_players()
    uid = str(user.id)
    p = players.get(uid)

    if not p:
        text = "No stats yet. Join a tournament to get started."
    else:
        text = (
            f\"📊 Stats for {p.get('username', user.full_name)}\\n\\n\"
            f\"Total buy-ins logged: ${p.get('total_buyins', 0):.2f}\\n\"
            f\"Tournaments joined: {p.get('entries', 0)}\\n\"
        )

    keyboard = [
        [InlineKeyboardButton("📜 View Tournaments", callback_data="menu_tournaments")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE, t_id: str):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    uid = str(user.id)

    t = find_tournament(t_id)
    if not t:
        await query.edit_message_text("That tournament is no longer available.")
        return

    players = get_players()
    market = get_market()

    if uid not in players:
        players[uid] = {
            "username": user.username or user.full_name,
            "joined_at": datetime.utcnow().isoformat(),
            "total_buyins": 0.0,
            "entries": 0,
        }

    buy_in = float(t["buy_in"])
    players[uid]["total_buyins"] = players[uid].get("total_buyins", 0.0) + buy_in
    players[uid]["entries"] = players[uid].get("entries", 0) + 1
    save_players(players)

    entry = {
        "user_id": uid,
        "username": user.username or user.full_name,
        "tournament_id": t["id"],
        "tournament_name": t["name"],
        "buy_in": buy_in,
        "timestamp": datetime.utcnow().isoformat(),
    }
    market["entries"].append(entry)
    save_market(market)

    prize_pool = buy_in * t.get("prize_pool_pct", 0.75)

    text = (
        f\"✅ Entry logged for {t['name']}.\\n\\n\"
        f\"Buy-in: ${buy_in:.2f}\\n\"
        f\"Prize pool contribution (@{t.get('prize_pool_pct', 0.75)*100:.0f}%): "
        f\"${prize_pool:.2f}\\n\\n\"
        "Use your real-world payment method as normal. "
        "This bot just tracks numbers for you and promoters."
    )

    keyboard = [
        [InlineKeyboardButton("📜 View Tournaments", callback_data="menu_tournaments")],
        [InlineKeyboardButton("📊 My Stats", callback_data="menu_stats")],
        [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "menu_tournaments":
        await tournaments_menu(update, context)
    elif data == "menu_main":
        await main_menu(update, context)
    elif data == "menu_stats":
        await stats_menu(update, context)
    elif data.startswith("join_"):
        t_id = data.split("join_", 1)[1]
        await handle_join(update, context, t_id)
    else:
        await query.answer("Unknown option", show_alert=True)


# ---------- MAIN APP ----------

async def run_bot():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(callbacks))

    logger.info("Cash Pool bot starting...")
    await app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_bot())
