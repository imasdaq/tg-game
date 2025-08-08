# -*- coding: utf-8 -*-
import json
from datetime import datetime
import os
import random
from typing import Dict, Any, Optional

from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

DATA_FILE = "game_data.json"

# Player storage: key = str(user_id), value = dict
players: Dict[str, Dict[str, Any]] = {}

# Keyboards
CLASS_KB = ReplyKeyboardMarkup(
    [["⚔️ Warrior", "🧙 Mage", "🕵️ Rogue"]],
    one_time_keyboard=True,
    resize_keyboard=True
)
MAIN_KB = ReplyKeyboardMarkup(
    [["🗺️ Adventure", "📊 Status"], 
     ["🎒 Inventory", "🧾 Quests"], 
     ["🛒 Shop", "🎰 Casino"],
     ["⚙️ Help"]],
    resize_keyboard=True
)

# Class base parameters
CLASS_STATS = {
    "⚔️ Warrior": {"hp": 110, "attack": 7, "defense": 4, "ability": "Power Strike"},
    "🧙 Mage": {"hp": 95, "attack": 9, "defense": 2, "ability": "Fire Blast"},
    "🕵️ Rogue": {"hp": 100, "attack": 7, "defense": 3, "ability": "Shadow Strike"},
}

# Shop (basic items)
SHOP_ITEMS = {
    "Minor Healing Potion": {"price": 15, "type": "consumable", "effect": {"heal": 35}},
    "Rune of Power": {"price": 30, "type": "consumable", "effect": {"attack_plus": 1}},
    "Leather Armor": {"price": 30, "type": "consumable", "effect": {"defense_plus": 1}},
}

# Casino constants
CASINO_GAMES = {
    "double": {"name": "🎯 Double", "multiplier": 2, "win_chance": 0.45, "min_bet": 5},
    "dice": {"name": "🎲 Dice", "multiplier": 1.5, "win_chance": 0.5, "min_bet": 5},
    "roulette": {"name": "🎡 Roulette", "multiplier": 2, "win_chance": 0.4, "min_bet": 5}
}

# ----------------------------- Saving utilities -----------------------------

def load_players() -> None:
    global players
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                players = json.load(f)
        except Exception:
            players = {}
    else:
        players = {}

def save_players() -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(players, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ----------------------------- Game logic --------------------------------

def get_xp_to_next(level: int) -> int:
    # Progression: 100, 150, 200, ...
    return 100 + (level - 1) * 50

def ensure_player(user_id: int, name: str) -> Dict[str, Any]:
    uid = str(user_id)
    if uid not in players:
        players[uid] = {
            "name": name,
            "class": None,
            "level": 1,
            "xp": 0,
            "hp": 100,
            "max_hp": 100,
            "attack": 5,
            "defense": 2,
            "gold": 50,  # Increased starting gold
            "inventory": {"Minor Healing Potion": 2},
            "quests": {},
            "last_casino_play": None
        }
        save_players()
    return players[uid]

def set_class(player: Dict[str, Any], class_name: str) -> None:
    stats = CLASS_STATS[class_name]
    player["class"] = class_name
    player["max_hp"] = stats["hp"]
    player["hp"] = stats["hp"]
    player["attack"] = stats["attack"]
    player["defense"] = stats["defense"]
    # Give starting quest
    if "rat_hunter" not in player["quests"]:
        player["quests"]["rat_hunter"] = {
            "title": "Rat Hunter",
            "desc": "Kill 3 rats in the vicinity.",
            "target_type": "rat",
            "required": 3,
            "progress": 0,
            "status": "active",
            "reward": {"xp": 100, "gold": 30, "item": "Minor Healing Potion"},
        }
    save_players()

def add_item(player: Dict[str, Any], item_name: str, count: int = 1) -> None:
    inv = player["inventory"]
    inv[item_name] = inv.get(item_name, 0) + count
    save_players()

def consume_item(player: Dict[str, Any], item_name: str, count: int = 1) -> bool:
    inv = player["inventory"]
    if inv.get(item_name, 0) >= count:
        inv[item_name] -= count
        if inv[item_name] <= 0:
            del inv[item_name]
        save_players()
        return True
    return False

def heal_player(player: Dict[str, Any], amount: int) -> int:
    before = player["hp"]
    player["hp"] = min(player["max_hp"], player["hp"] + amount)
    save_players()
    return player["hp"] - before

def grant_rewards(player: Dict[str, Any], xp: int, gold: int, loot: Optional[str] = None) -> str:
    player["xp"] += xp
    player["gold"] += gold
    loot_text = ""
    if loot:
        add_item(player, loot, 1)
        loot_text = f"\nLoot: {loot}"
    level_up_text = check_level_up(player)
    save_players()
    return f"+{xp} XP, +{gold} gold.{loot_text}{level_up_text}"

def check_level_up(player: Dict[str, Any]) -> str:
    text = ""
    while player["xp"] >= get_xp_to_next(player["level"]):
        player["xp"] -= get_xp_to_next(player["level"])
        player["level"] += 1
        # Stats growth
        player["max_hp"] += 8
        player["attack"] += 1
        if player["level"] % 2 == 0:
            player["defense"] += 1
        player["hp"] = player["max_hp"]
        text += f"\n🔺 Level up! Now level {player['level']}. HP restored."
    if text:
        save_players()
    return text

def generate_enemy(level: int) -> Dict[str, Any]:
    # Enemy types with base parameters
    enemy_types = [
        {"type": "rat", "name": "Rat", "hp": 30, "attack": 4, "defense": 1, "xp": 25, "gold": (5, 10), "loot": [None, None, "Minor Healing Potion"]},
        {"type": "goblin", "name": "Goblin", "hp": 45, "attack": 6, "defense": 2, "xp": 40, "gold": (8, 18), "loot": [None, "Minor Healing Potion", "Rune of Power"]},
        {"type": "wolf", "name": "Wolf", "hp": 55, "attack": 7, "defense": 3, "xp": 55, "gold": (10, 20), "loot": [None, "Minor Healing Potion"]},
    ]
    base = random.choice(enemy_types)
    # Scaling by level
    scale = max(0, level - 1)
    enemy = {
        "type": base["type"],
        "name": base["name"],
        "hp": base["hp"] + 5 * scale,
        "max_hp": base["hp"] + 5 * scale,
        "attack": base["attack"] + scale * 2,  # Stronger attack increase
        "defense": base["defense"] + (scale // 2),
        "xp": base["xp"] + 10 * scale,
        "gold": random.randint(*base["gold"]) + 2 * scale,
        "loot": random.choice(base["loot"]),
    }
    return enemy

def dmg_roll(atk: int, df: int, spread: int = 2) -> int:
    # Damage now depends on attack-defense difference
    raw = atk + random.randint(0, spread) - max(0, df - 2)  # Defense reduces damage but no more than by 2
    return max(1, raw)

def ability_description(class_name: str) -> str:
    if class_name == "⚔️ Warrior":
        return "Power Strike: deal double damage once per battle."
    if class_name == "🧙 Mage":
        return "Fire Blast: 15 pure damage once per battle."
    if class_name == "🕵️ Rogue":
        return "Shadow Strike: attack ignoring defense once per battle."
    return ""

def build_battle_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗡️ Attack", callback_data="battle:attack"),
         InlineKeyboardButton("✨ Ability", callback_data="battle:ability")],
        [InlineKeyboardButton("🧪 Potion", callback_data="battle:potion"),
         InlineKeyboardButton("🏃 Run", callback_data="battle:run")],
    ])

def build_shop_kb() -> InlineKeyboardMarkup:
    buttons = []
    for item_name, meta in SHOP_ITEMS.items():
        buttons.append([InlineKeyboardButton(f"Buy: {item_name} ({meta['price']}💰)", callback_data=f"shop:buy:{item_name}")])
    buttons.append([InlineKeyboardButton("Close", callback_data="shop:close")])
    return InlineKeyboardMarkup(buttons)

def battle_text(player: Dict[str, Any], enemy: Dict[str, Any], log: str = "") -> str:
    return (
        f"⚔️ Battle: {enemy['name']}\n"
        f"Enemy HP: {enemy['hp']}/{enemy['max_hp']}\n"
        f"You HP: {player['hp']}/{player['max_hp']}\n"
        f"Attack/Defense: {player['attack']}/{player['defense']}\n\n"
        f"{log}"
    )

def build_casino_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    buttons = []
    for game_type, game in CASINO_GAMES.items():
        can_play = player["gold"] >= game["min_bet"]
        text = f"{game['name']} (min {game['min_bet']}💰)" if can_play else f"{game['name']} ❌"
        callback = f"casino:{game_type}" if can_play else "casino:no_money"
        buttons.append([InlineKeyboardButton(text, callback_data=callback)])
    buttons.append([InlineKeyboardButton("💰 Balance", callback_data="casino:balance")])
    buttons.append([InlineKeyboardButton("🚪 Exit", callback_data="casino:exit")])
    return InlineKeyboardMarkup(buttons)

def play_casino_game(player: Dict[str, Any], game_type: str, bet: int) -> Dict[str, Any]:
    """Main casino game logic"""
    game = CASINO_GAMES[game_type]
    
    if bet < game["min_bet"]:
        return {"success": False, "message": f"❌ Minimum bet: {game['min_bet']} gold"}
    
    if player["gold"] < bet:
        return {"success": False, "message": "❌ Not enough gold!"}
    
    # Cooldown check (every 30 seconds)
    last_play = player.get("last_casino_play")
    if last_play:
        last_play = datetime.fromisoformat(last_play)
        elapsed = (datetime.now() - last_play).total_seconds()
        if elapsed < 30:
            return {"success": False, "message": f"⏳ Wait {int(30 - elapsed)} seconds before next game"}
    
    player["gold"] -= bet
    player["last_casino_play"] = datetime.now().isoformat()
    
    # Game logic
    if game_type == "double":
        if random.random() < game["win_chance"]:
            prize = bet * game["multiplier"]
            player["gold"] += prize
            return {"success": True, "message": f"🎉 Win! Won {prize} gold!", "prize": prize}
        return {"success": False, "message": f"💸 Lost! Lost {bet} gold."}
    
    elif game_type == "dice":
        player_roll = random.randint(1, 6)
        casino_roll = random.randint(1, 6)
        if player_roll > casino_roll:
            prize = int(bet * game["multiplier"])
            player["gold"] += prize
            return {"success": True, "message": f"🎲 You: {player_roll} | Casino: {casino_roll}\n🏆 Won {prize} gold!"}
        elif player_roll == casino_roll:
            player["gold"] += bet
            return {"success": None, "message": f"🎲 You: {player_roll} | Casino: {casino_roll}\n🤝 Draw! Bet returned."}
        else:
            return {"success": False, "message": f"🎲 You: {player_roll} | Casino: {casino_roll}\n💸 Lost {bet} gold."}
    
    elif game_type == "roulette":
        number = random.randint(0, 36)
        color = "🔴" if number % 2 == 1 else "⚫" if number != 0 else "🟢"
        if number == 0:
            return {"success": False, "message": f"🎡 Landed: {color}0\n💸 Lost {bet} gold!"}
        elif (color == "🔴" and random.random() < game["win_chance"]) or (color == "⚫" and random.random() < game["win_chance"]):
            prize = bet * game["multiplier"]
            player["gold"] += prize
            return {"success": True, "message": f"🎡 Landed: {color}{number}\n🎉 Won {prize} gold!"}
        else:
            return {"success": False, "message": f"🎡 Landed: {color}{number}\n💸 Lost {bet} gold."}
    
    save_players()
    return {"success": False, "message": "⚠️ Game error"}

# ----------------------------- Command handlers -------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Hero")

    if player["class"] is None:
        await update.message.reply_text(
            f"Hello, {player['name']}! Choose your class:",
            reply_markup=CLASS_KB
        )
        context.user_data["state"] = "choose_class"
    else:
        await update.message.reply_text(
            f"✨ Welcome back, {player['name']} ({player['class']})!\n"
            f"💫 Ability: {ability_description(player['class'])}\n"
            "Choose action:",
            reply_markup=MAIN_KB
        )
        context.user_data["state"] = "idle"

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 <b>Available commands:</b>\n\n"
        "⚔️ <b>Main:</b>\n"
        "/start - Start game\n"
        "/status - Show status\n"
        "/inventory - Open inventory\n\n"
        "🌍 <b>Game:</b>\n"
        "/adventure - Go on adventure\n"
        "/quests - Active quests\n"
        "/shop - Visit shop\n"
        "/casino - Play casino\n\n"
        "🧪 <b>Items:</b>\n"
        "/use_potion - Use potion\n\n"
        "🛠️ <b>Other:</b>\n"
        "/help - Show this message"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First press /start")
        return
    p = players[uid]
    text = (
        f"📊 <b>Status {p['name']} ({p['class'] or 'No class'})</b>\n\n"
        f"⚔️ Level: <b>{p['level']}</b> ({p['xp']}/{get_xp_to_next(p['level'])} XP)\n"
        f"❤️ HP: <b>{p['hp']}/{p['max_hp']}</b>\n"
        f"🗡️ Attack: <b>{p['attack']}</b> 🛡️ Defense: <b>{p['defense']}</b>\n"
        f"💰 Gold: <b>{p['gold']}</b>\n\n"
        f"✨ Ability: {ability_description(p['class']) if p['class'] else '-'}"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First press /start")
        return
    p = players[uid]
    if not p["inventory"]:
        await update.message.reply_text("🎒 <b>Your inventory is empty.</b>", parse_mode="HTML", reply_markup=MAIN_KB)
        return
    
    items = "\n".join(f"▪️ {item} ×{count}" for item, count in p["inventory"].items())
    await update.message.reply_text(
        f"🎒 <b>Inventory:</b>\n\n{items}\n\n"
        "ℹ️ Use /use_potion to heal",
        parse_mode="HTML",
        reply_markup=MAIN_KB
    )

async def use_potion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First press /start")
        return
    p = players[uid]
    item = "Minor Healing Potion"
    if p["hp"] >= p["max_hp"]:
        await update.message.reply_text("❤️ You're at full health!")
        return
    if consume_item(p, item, 1):
        healed = heal_player(p, 35)
        await update.message.reply_text(f"🧪 You drank a potion and healed {healed} HP. Now: {p['hp']}/{p['max_hp']}")
    else:
        await update.message.reply_text("❌ No Minor Healing Potions in inventory.")

async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First press /start")
        return
    p = players[uid]
    q = p["quests"]
    if not q:
        await update.message.reply_text("📜 You don't have any quests yet.", reply_markup=MAIN_KB)
        return
    
    quests_text = []
    for quest in q.values():
        status = "✅" if quest["status"] == "completed" else "⌛"
        quests_text.append(
            f"{status} <b>{quest['title']}</b>\n"
            f"{quest['desc']}\n"
            f"Progress: {quest['progress']}/{quest['required']}\n"
        )
    
    await update.message.reply_text(
        "📜 <b>Active quests:</b>\n\n" + "\n".join(quests_text),
        parse_mode="HTML",
        reply_markup=MAIN_KB
    )

async def adventure_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First press /start")
        return
    
    # Check for active battle or merchant
    if context.user_data.get("battle") or context.user_data.get("merchant_active"):
        await update.message.reply_text(
            "⚠️ First complete current event (battle or trade)!",
            reply_markup=MAIN_KB
        )
        return
    
    # Cooldown check
    last_adventure = context.user_data.get("last_adventure")
    if last_adventure:
        cooldown = 6
        elapsed = (datetime.now() - last_adventure).total_seconds()
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            await update.message.reply_text(
                f"You're tired. Rest for {remaining} more seconds.",
                reply_markup=MAIN_KB
            )
            return
    
    p = players[uid]
    context.user_data["last_adventure"] = datetime.now()
    
    event = random.choice(["fight", "gold", "item", "merchant"])
    if event == "fight":
        enemy = generate_enemy(p["level"])
        context.user_data["battle"] = {
            "enemy": enemy,
            "ability_used": False,
            "message_id": None,
            "chat_id": update.effective_chat.id,
        }
        msg = await update.message.reply_text(
            battle_text(p, enemy, "An enemy attacks you! What will you do?"),
            reply_markup=build_battle_kb()
        )
        context.user_data["battle"]["message_id"] = msg.message_id
    elif event == "gold":
        gain = random.randint(10, 25)
        p["gold"] += gain
        save_players()
        await update.message.reply_text(f"You found a bag of gold: +{gain} 💰. Now you have {p['gold']} gold.")
    elif event == "item":
        item = random.choice(list(SHOP_ITEMS.keys()))
        add_item(p, item, 1)
        await update.message.reply_text(f"You found an item: {item}! It's added to your inventory.")
    elif event == "merchant":
        context.user_data["merchant_active"] = True
        await update.message.reply_text(
            "You encountered a wandering merchant:",
            reply_markup=build_shop_kb()
        )

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Merchant's shop:", reply_markup=build_shop_kb())

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("First press /start")
        return
    
    p = players[uid]
    data = query.data # shop:buy:ITEM or shop:close

    if data == "shop:close":
        context.user_data.pop("merchant_active", None)
        await query.edit_message_text("The merchant disappears into the mist...")
        return

    _, action, item_name = data.split(":", 2)
    if action == "buy":
        if item_name not in SHOP_ITEMS:
            await query.edit_message_text("No such item.")
            return
        
        price = SHOP_ITEMS[item_name]["price"]
        if p["gold"] < price:
            await query.edit_message_text(f"Not enough gold. Need {price}💰, you have {p['gold']}💰.")
            return

        p["gold"] -= price
        effect = SHOP_ITEMS[item_name]["effect"]
        
        if "heal" in effect and SHOP_ITEMS[item_name]["type"] == "consumable" and item_name == "Minor Healing Potion":
            add_item(p, item_name, 1)
            await query.edit_message_text(
                f"You bought: {item_name}. Inventory updated! Gold: {p['gold']}.",
                reply_markup=build_shop_kb()  # Keep shop open
            )
        else:
            if "attack_plus" in effect:
                p["attack"] += effect["attack_plus"]
            if "defense_plus" in effect:
                p["defense"] += effect["defense_plus"]
            save_players()
            await query.edit_message_text(
                f"You bought and used: {item_name}. Your power grows! Gold: {p['gold']}.",
                reply_markup=build_shop_kb()  # Keep shop open
            )

async def casino_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /casino command"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First start the game with /start")
        return
    
    p = players[uid]
    await update.message.reply_text(
        f"🎰 <b>Welcome to the casino!</b>\n"
        f"💰 Your balance: {p['gold']} gold\n\n"
         "🎮 Enter the amount of gold you want to bet:",
        parse_mode="HTML",
        reply_markup=build_casino_kb(p)
    )

async def casino_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for casino bet input"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("First start the game with /start")
        return
    
    p = players[uid]
    text = update.message.text.strip()
    
    try:
        if "%" in text:
            percent = float(text.replace("%", "").strip())
            if percent <= 0 or percent > 100:
                raise ValueError
            bet = int(p["gold"] * (percent / 100))
        else:
            bet = int(text)
    except ValueError:
        await update.message.reply_text("❌ Enter a number or percentage (e.g.: 50 or 25%)")
        return
    
    min_bet = min(game["min_bet"] for game in CASINO_GAMES.values())
    if bet < min_bet:
        await update.message.reply_text(f"❌ Minimum bet: {min_bet} gold")
        return
    if bet > p["gold"]:
        await update.message.reply_text(f"❌ Not enough gold. Your balance: {p['gold']}")
        return
    
    context.user_data["casino_bet"] = bet
    await show_casino_games(update, context)

async def show_casino_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show games after bet input"""
    bet = context.user_data["casino_bet"]
    
    buttons = [
        [InlineKeyboardButton(CASINO_GAMES["double"]["name"], callback_data="casino:double")],
        [InlineKeyboardButton(CASINO_GAMES["dice"]["name"], callback_data="casino:dice")],
        [InlineKeyboardButton(CASINO_GAMES["roulette"]["name"], callback_data="casino:roulette")],
        [InlineKeyboardButton("❌ Cancel", callback_data="casino:exit")]
    ]
    
    await update.message.reply_text(
        f"💰 Your bet: <b>{bet}</b> gold\n"
        "🎮 Choose a game:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def casino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for casino inline buttons"""
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("❌ First start the game (/start)")
        return
    
    p = players[uid]
    data = query.data.split(":")
    
    if data[1] == "exit":
        await query.edit_message_text("🚪 You left the casino. Good luck on your adventures!")
        return
    elif data[1] == "balance":
        await query.answer(f"Your balance: {p['gold']} gold", show_alert=True)
        return
    elif data[1] == "no_money":
        await query.answer("❌ Not enough gold for this game!", show_alert=True)
        return
    
    # Determine bet
    bet = context.user_data.get("casino_bet", 10)  # Default 10 if bet wasn't set
    game_type = data[1]
    
    result = play_casino_game(p, game_type, bet)
    save_players()
    
    if "Wait" in result["message"]:
        await query.answer(result["message"], show_alert=True)
        return
    
    # Form full message with result
    message = (
        f"🎰 <b>{CASINO_GAMES[game_type]['name']}</b>\n"
        f"💵 Bet: <b>{bet}</b> gold\n\n"
        f"{result['message']}\n\n"
        f"💰 Current balance: <b>{p['gold']}</b> gold\n\n"
    )
    
    if result["success"] is False:
        message += "😔 Bad luck... Try again!"
    elif result["success"] is True:
        message += "🎉 Great result! Want to play again?"
    else:
        message += "🤝 Draw! Try again."
    
    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=build_casino_kb(p)
    )

# ----------------------------- Battle: callbacks -------------------------------

async def battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("First press /start")
        return
    
    p = players[uid]
    state = context.user_data.get("battle")
    if not state:
        await query.edit_message_text("You're not in battle now.")
        return

    enemy = state["enemy"]
    action = query.data # battle:attack | battle:ability | battle:potion | battle:run

    log = ""
    if action == "battle:attack":
        dmg = dmg_roll(p["attack"], enemy["defense"])
        enemy["hp"] -= dmg
        log += f"You attacked {enemy['name']} and dealt {dmg} damage.\n"
    elif action == "battle:ability":
        if state.get("ability_used"):
            log += "Ability already used in this battle!\n"
        else:
            cls = p["class"]
            if cls == "⚔️ Warrior":
                dmg = dmg_roll(p["attack"], enemy["defense"]) * 2
                enemy["hp"] -= dmg
                log += f"You used 'Power Strike' and dealt {dmg} damage!\n"
            elif cls == "🧙 Mage":
                dmg = 15
                enemy["hp"] -= dmg
                log += f"You used 'Fire Blast' and dealt {dmg} pure damage!\n"
            elif cls == "🕵️ Rogue":
                dmg = max(1, p["attack"] + random.randint(0, 2)) # ignore defense
                enemy["hp"] -= dmg
                log += f"You used 'Shadow Strike' and dealt {dmg} damage (ignores defense)!\n"
            else:
                log += "Your class has no special ability.\n"
            state["ability_used"] = True
    elif action == "battle:potion":
        if consume_item(p, "Minor Healing Potion", 1):
            healed = heal_player(p, 35)
            log += f"You drank a potion and healed {healed} HP.\n"
        else:
            log += "You don't have Minor Healing Potions.\n"
    elif action == "battle:run":
        if random.random() < 0.6:
            await query.edit_message_text("You successfully fled from battle.")
            context.user_data.pop("battle", None)
            return
        else:
            log += "Failed to run away!\n"

    # Check enemy death
    if enemy["hp"] <= 0:
        loot_text = grant_rewards(p, enemy["xp"], enemy["gold"], enemy.get("loot"))
        q = p["quests"].get("rat_hunter")
        quest_text = ""
        if q and q["status"] == "active" and enemy["type"] == q["target_type"]:
            q["progress"] += 1
            if q["progress"] >= q["required"]:
                q["status"] = "completed"
                rew = q["reward"]
                add_text = grant_rewards(p, rew["xp"], rew["gold"], rew["item"])
                quest_text = f"\n✅ Quest '{q['title']}' completed! {add_text}"
            save_players()
        else:
            quest_text = f"\nQuest '{q['title']}': progress {q['progress']}/{q['required']}."
            save_players()

        await query.edit_message_text(
            f"You defeated {enemy['name']}! {loot_text}{quest_text}"
        )
        context.user_data.pop("battle", None)
        return

    # Enemy turn (if alive)
    if enemy["hp"] > 0 and action != "battle:run":
        edmg = dmg_roll(enemy["attack"], p["defense"])
        p["hp"] -= edmg
        save_players()
        log += f"{enemy['name']} attacks and deals {edmg} damage.\n"

    # Check player death
    if p["hp"] <= 0:
        loss_gold = min(10, p["gold"])
        p["gold"] -= loss_gold
        p["hp"] = max(1, p["max_hp"] // 2)
        save_players()
        await query.edit_message_text(
            f"You fell in battle... Lost {loss_gold} gold. "
            f"You come to your senses with {p['hp']}/{p['max_hp']} HP."
        )
        context.user_data.pop("battle", None)
        return

    # Update battle text
    try:
        await query.edit_message_text(
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )
    except Exception:
        await query.message.reply_text(
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )

# ----------------------------- Class choice/texts ---------------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Hero")

    state = context.user_data.get("state", "idle")

    if state == "choose_class":
        choice = msg.text.strip()
        if choice in CLASS_STATS:
            set_class(player, choice)
            context.user_data["state"] = "idle"
            await msg.reply_text(
                f"You chose class {choice}.\n"
                f"Ability: {ability_description(choice)}\n"
                f"Good luck on your adventures!",
                reply_markup=MAIN_KB
            )
        else:
            await msg.reply_text("Please choose a class from the buttons provided.", reply_markup=CLASS_KB)
        return

    # Main menu
    if msg.text == "📊 Status":
        await status_cmd(update, context)
    elif msg.text == "🎒 Inventory":
        await inventory_cmd(update, context)
    elif msg.text == "🗺️ Adventure":
        await adventure_cmd(update, context)
    elif msg.text == "🧾 Quests":
        await quests_cmd(update, context)
    elif msg.text == "🛒 Shop":
        await shop_cmd(update, context)
    elif msg.text == "🎰 Casino":
        await casino_cmd(update, context)
    elif msg.text == "⚙️ Help":
        await help_cmd(update, context)
    else:
        await msg.reply_text("I don't understand. Use the buttons or /help.", reply_markup=MAIN_KB)

# --------------------------------- Main --------------------------------------

def main():
    load_players()
    # Replace with your actual Telegram Bot Token
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("use_potion", use_potion_cmd))
    app.add_handler(CommandHandler("quests", quests_cmd))
    app.add_handler(CommandHandler("adventure", adventure_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("casino", casino_cmd))
    
    # Casino bet handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(\d+|(\d+%)$)'),
        casino_bet_input
    ))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(casino_callback, pattern=r"^casino:"))
    
    # Text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
