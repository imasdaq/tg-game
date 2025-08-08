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

# Хранилище игроков: key = str(user_id), value = dict
players: Dict[str, Dict[str, Any]] = {}

# Клавиатуры
CLASS_KB = ReplyKeyboardMarkup(
    [["⚔️ Воин", "🧙 Маг", "🕵️ Вор"]],
    one_time_keyboard=True,
    resize_keyboard=True
)
MAIN_KB = ReplyKeyboardMarkup(
    [["🗺️ Приключение", "📊 Статус"], ["🎒 Инвентарь", "🧾 Квесты"], ["🛒 Магазин", "⚙️ Помощь"]],
    resize_keyboard=True
)

# Базовые параметры классов
CLASS_STATS = {
    "⚔️ Воин": {"hp": 110, "attack": 7, "defense": 4, "ability": "Мощный удар"},
    "🧙 Маг": {"hp": 95, "attack": 9, "defense": 2, "ability": "Огненная вспышка"},
    "🕵️ Вор": {"hp": 100, "attack": 7, "defense": 3, "ability": "Теневая атака"},
}

# Магазин (базовый ассортимент)
SHOP_ITEMS = {
    "Малое зелье лечения": {"price": 15, "type": "consumable", "effect": {"heal": 35}},
    "Руна силы": {"price": 30, "type": "consumable", "effect": {"attack_plus": 1}},
    "Кожаная броня": {"price": 30, "type": "consumable", "effect": {"defense_plus": 1}},
}

# ----------------------------- Утилиты сохранения -----------------------------

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

# ----------------------------- Игровая логика --------------------------------

def get_xp_to_next(level: int) -> int:
    # Прогрессия: 100, 150, 200, ...
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
            "gold": 25,
            "inventory": {"Малое зелье лечения": 2},
            "quests": {},
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
    # Выдать стартовый квест
    if "rat_hunter" not in player["quests"]:
        player["quests"]["rat_hunter"] = {
            "title": "Крысолов",
            "desc": "Убей 3 крыс в окрестностях.",
            "target_type": "rat",
            "required": 3,
            "progress": 0,
            "status": "active",
            "reward": {"xp": 100, "gold": 30, "item": "Малое зелье лечения"},
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
        loot_text = f"\nДобыча: {loot}"
    level_up_text = check_level_up(player)
    save_players()
    return f"+{xp} XP, +{gold} золота.{loot_text}{level_up_text}"

def check_level_up(player: Dict[str, Any]) -> str:
    text = ""
    while player["xp"] >= get_xp_to_next(player["level"]):
        player["xp"] -= get_xp_to_next(player["level"])
        player["level"] += 1
        # Рост характеристик
        player["max_hp"] += 8
        player["attack"] += 1
        if player["level"] % 2 == 0:
            player["defense"] += 1
        player["hp"] = player["max_hp"]
        text += f"\n🔺 Уровень повышен! Теперь {player['level']} уровень. HP восстановлено."
    if text:
        save_players()
    return text

def generate_enemy(level: int) -> Dict[str, Any]:
    # Типы врагов с базовыми параметрами
    enemy_types = [
        {"type": "rat", "name": "Крыса", "hp": 30, "attack": 4, "defense": 1, "xp": 25, "gold": (5, 10), "loot": [None, None, "Малое зелье лечения"]},
        {"type": "goblin", "name": "Гоблин", "hp": 45, "attack": 6, "defense": 2, "xp": 40, "gold": (8, 18), "loot": [None, "Малое зелье лечения", "Руна силы"]},
        {"type": "wolf", "name": "Волк", "hp": 55, "attack": 7, "defense": 3, "xp": 55, "gold": (10, 20), "loot": [None, "Малое зелье лечения"]},
    ]
    base = random.choice(enemy_types)
    # Масштабирование по уровню
    scale = max(0, level - 1)
    enemy = {
        "type": base["type"],
        "name": base["name"],
        "hp": base["hp"] + 5 * scale,
        "max_hp": base["hp"] + 5 * scale,
        "attack": base["attack"] + scale,
        "defense": base["defense"] + (scale // 2),
        "xp": base["xp"] + 10 * scale,
        "gold": random.randint(*base["gold"]) + 2 * scale,
        "loot": random.choice(base["loot"]),
    }
    return enemy

def dmg_roll(atk: int, df: int, spread: int = 2) -> int:
    raw = atk + random.randint(0, spread) - df
    return max(1, raw)

def ability_description(class_name: str) -> str:
    if class_name == "⚔️ Воин":
        return "Мощный удар: нанесение двойного урона один раз за бой."
    if class_name == "🧙 Маг":
        return "Огненная вспышка: 15 чистого урона один раз за бой."
    if class_name == "🕵️ Вор":
        return "Теневая атака: удар, игнорирующий защиту, один раз за бой."
    return ""

# ----------------------------- Хендлеры команд -------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Герой")

    if player["class"] is None:
        await update.message.reply_text(
            f"Привет, {player['name']}! Выбери свой класс:",
            reply_markup=CLASS_KB
        )
        context.user_data["state"] = "choose_class"
    else:
        await update.message.reply_text(
            f"С возвращением, {player['name']} ({player['class']})!\n"
            f"Твоя способность: {ability_description(player['class'])}\nВыбирай действие:",
            reply_markup=MAIN_KB
        )
        context.user_data["state"] = "idle"

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Команды:\n"
        "/start — начать или продолжить\n"
        "/status — характеристики\n"
        "/inventory — инвентарь\n"
        "/use_potion — выпить малое зелье лечения\n"
        "/adventure — отправиться в приключение (случайное событие)\n"
        "/quests — квесты и прогресс\n"
        "/shop — открыть магазин\n"
        "/help — помощь\n\n"
        "Подсказка: используй кнопки внизу для удобства."
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    text = (
        f"📊 Статус {p['name']} ({p['class'] or 'Без класса'})\n"
        f"Уровень: {p['level']} ({p['xp']}/{get_xp_to_next(p['level'])} XP)\n"
        f"HP: {p['hp']}/{p['max_hp']}\n"
        f"Атака: {p['attack']} Защита: {p['defense']}\n"
        f"Золото: {p['gold']}\n"
        f"Способность: {ability_description(p['class']) if p['class'] else '-'}"
    )
    await update.message.reply_text(text, reply_markup=MAIN_KB)

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    if not p["inventory"]:
        await update.message.reply_text("Твой инвентарь пуст.", reply_markup=MAIN_KB)
        return
    lines = ["🎒 Инвентарь:"]
    for item, cnt in p["inventory"].items():
        lines.append(f"- {item} x{cnt}")
    lines.append("\nПодсказка: попробуй /use_potion, чтобы восстановить здоровье.")
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_KB)

async def use_potion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    item = "Малое зелье лечения"
    if p["hp"] >= p["max_hp"]:
        await update.message.reply_text("У тебя полное здоровье.")
        return
    if consume_item(p, item, 1):
        healed = heal_player(p, 35)
        await update.message.reply_text(f"Ты выпил зелье и восстановил {healed} HP. Текущее HP: {p['hp']}/{p['max_hp']}")
    else:
        await update.message.reply_text("Нет Малых зелий лечения в инвентаре.")

async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    q = p["quests"]
    if not q:
        await update.message.reply_text("Квестов пока нет.", reply_markup=MAIN_KB)
        return
    lines = ["🧾 Квесты:"]
    for key, quest in q.items():
        lines.append(
            f"- {quest['title']} [{quest['status']}]: {quest['progress']}/{quest['required']} — {quest['desc']}"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=MAIN_KB)

# ----------------------------- Приключения/События ---------------------------

def build_battle_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗡️ Атака", callback_data="battle:attack"),
         InlineKeyboardButton("✨ Способность", callback_data="battle:ability")],
        [InlineKeyboardButton("🧪 Зелье", callback_data="battle:potion"),
         InlineKeyboardButton("🏃 Бег", callback_data="battle:run")],
    ])

def build_shop_kb() -> InlineKeyboardMarkup:
    buttons = []
    for item_name, meta in SHOP_ITEMS.items():
        buttons.append([InlineKeyboardButton(f"Купить: {item_name} ({meta['price']}💰)", callback_data=f"shop:buy:{item_name}")])
    buttons.append([InlineKeyboardButton("Закрыть", callback_data="shop:close")])
    return InlineKeyboardMarkup(buttons)

def battle_text(player: Dict[str, Any], enemy: Dict[str, Any], log: str = "") -> str:
    return (
        f"⚔️ Бой: {enemy['name']}\n"
        f"Враг HP: {enemy['hp']}/{enemy['max_hp']}\n"
        f"Ты HP: {player['hp']}/{player['max_hp']}\n"
        f"Атака/Защита: {player['attack']}/{player['defense']}\n\n"
        f"{log}"
    )

async def adventure_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    # Проверка кулдауна
    last_adventure = context.user_data.get("last_adventure")
    if last_adventure:
        cooldown = 30  # 30 секунд кулдауна
        elapsed = (datetime.now() - last_adventure).total_seconds()
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            await update.message.reply_text(
                f"Ты устал и не готов к новым приключениям. Отдохни ещё {remaining} секунд.",
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
            battle_text(p, enemy, "На тебя нападает враг! Что будешь делать?"),
            reply_markup=build_battle_kb()
        )
        context.user_data["battle"]["message_id"] = msg.message_id
    elif event == "gold":
        gain = random.randint(10, 25)
        p["gold"] += gain
        save_players()
        await update.message.reply_text(f"Ты нашёл мешочек золота: +{gain} 💰. Теперь у тебя {p['gold']} золота.")
    elif event == "item":
        item = random.choice(list(SHOP_ITEMS.keys()))
        add_item(p, item, 1)
        await update.message.reply_text(f"Ты нашёл предмет: {item}! Он добавлен в инвентарь.")
    elif event == "merchant":
        await update.message.reply_text("Тебе повстречался странствующий торговец:", reply_markup=build_shop_kb())


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Лавка торговца:", reply_markup=build_shop_kb())

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("Сначала нажми /start")
        return
    p = players[uid]
    data = query.data # shop:buy:ITEM or shop:close

    if data == "shop:close":
        await query.edit_message_text("Торговец уходит в туман...")
        return

    _, action, item_name = data.split(":", 2)
    if action == "buy":
        if item_name not in SHOP_ITEMS:
            await query.edit_message_text("Такого товара нет.")
            return
        price = SHOP_ITEMS[item_name]["price"]
        if p["gold"] < price:
            await query.edit_message_text(f"Не хватает золота. Нужно {price}💰, у тебя {p['gold']}💰.")
            return

        p["gold"] -= price
        effect = SHOP_ITEMS[item_name]["effect"]
        # Предметы сразу применяются, чтобы упростить механику, кроме зелий — они в инвентарь
        if "heal" in effect and SHOP_ITEMS[item_name]["type"] == "consumable" and item_name == "Малое зелье лечения":
            add_item(p, item_name, 1)
            await query.edit_message_text(f"Ты купил: {item_name}. В инвентаре пополнение! Золото: {p['gold']}.")
        else:
            # Применяем постоянные бафы
            if "attack_plus" in effect:
                p["attack"] += effect["attack_plus"]
            if "defense_plus" in effect:
                p["defense"] += effect["defense_plus"]
            save_players()
            await query.edit_message_text(f"Ты купил и использовал: {item_name}. Твоя сила растёт! Золото: {p['gold']}.")

# ----------------------------- Бой: callback-и -------------------------------

async def battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("Сначала нажми /start")
        return
    p = players[uid]
    state = context.user_data.get("battle")
    if not state:
        await query.edit_message_text("Сейчас ты не в бою.")
        return

    enemy = state["enemy"]
    action = query.data # battle:attack | battle:ability | battle:potion | battle:run

    log = ""
    # Ход игрока
    if action == "battle:attack":
        dmg = dmg_roll(p["attack"], enemy["defense"])
        enemy["hp"] -= dmg
        log += f"Ты атаковал {enemy['name']} и нанёс {dmg} урона.\n"
    elif action == "battle:ability":
        if state.get("ability_used"):
            log += "Способность уже использована в этом бою!\n"
        else:
            cls = p["class"]
            if cls == "⚔️ Воин":
                dmg = dmg_roll(p["attack"], enemy["defense"]) * 2
                enemy["hp"] -= dmg
                log += f"Ты применил 'Мощный удар' и нанёс {dmg} урона!\n"
            elif cls == "🧙 Маг":
                dmg = 15
                enemy["hp"] -= dmg
                log += f"Ты применил 'Огненная вспышка' и нанёс {dmg} чистого урона!\n"
            elif cls == "🕵️ Вор":
                dmg = max(1, p["attack"] + random.randint(0, 2)) # игнор брони
                enemy["hp"] -= dmg
                log += f"Ты применил 'Теневая атака' и нанёс {dmg} урона (игнор брони)!\n"
            else:
                log += "Твой класс не имеет особой способности.\n"
            state["ability_used"] = True
    elif action == "battle:potion":
        if consume_item(p, "Малое зелье лечения", 1):
            healed = heal_player(p, 35)
            log += f"Ты выпил зелье и восстановил {healed} HP.\n"
        else:
            log += "У тебя нет Малых зелий лечения.\n"
    elif action == "battle:run":
        # Шанс на побег
        if random.random() < 0.6:
            await query.edit_message_text("Ты успешно сбежал с поля боя.")
            context.user_data["battle"] = None
            return
        else:
            log += "Не удалось сбежать!\n"

    # Проверка смерти врага
    if enemy["hp"] <= 0:
        # Награда
        loot_text = grant_rewards(p, enemy["xp"], enemy["gold"], enemy.get("loot"))
        # Прогресс квеста
        q = p["quests"].get("rat_hunter")
        quest_text = ""
        if q and q["status"] == "active" and enemy["type"] == q["target_type"]:
            q["progress"] += 1
            if q["progress"] >= q["required"]:
                q["status"] = "completed"
                rew = q["reward"]
                add_text = grant_rewards(p, rew["xp"], rew["gold"], rew["item"])
                quest_text = f"\n✅ Квест '{q['title']}' выполнен! {add_text}"
            save_players()
        else:
            quest_text = f"\nКвест '{q['title']}': прогресс {q['progress']}/{q['required']}."
            save_players()

        await query.edit_message_text(
            f"Ты победил {enemy['name']}! {loot_text}{quest_text}"
        )
        context.user_data["battle"] = None
        return

    # Ход врага (если жив)
    if enemy["hp"] > 0 and action != "battle:run":
        edmg = dmg_roll(enemy["attack"], p["defense"])
        p["hp"] -= edmg
        save_players()
        log += f"{enemy['name']} атакует и наносит {edmg} урона.\n"

    # Проверка смерти игрока
    if p["hp"] <= 0:
        loss_gold = min(10, p["gold"])
        p["gold"] -= loss_gold
        # Респавн: половина HP
        p["hp"] = max(1, p["max_hp"] // 2)
        save_players()
        await query.edit_message_text(
            f"Ты пал в бою... Потеряно {loss_gold} золота. "
            f"Ты приходишь в себя с {p['hp']}/{p['max_hp']} HP."
        )
        context.user_data["battle"] = None
        return

    # Обновляем текст боя
    try:
        await query.edit_message_text(
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )
    except Exception:
        # Если редактирование не удалось — просто отправим новое сообщение
        await query.message.reply_text(
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )

# ----------------------------- Выбор класса/тексты ---------------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обработка текстовых кнопок главного меню и выбора класса
    msg = update.message
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Герой")

    state = context.user_data.get("state", "idle")

    if state == "choose_class":
        choice = msg.text.strip()
        if choice in CLASS_STATS:
            set_class(player, choice)
            context.user_data["state"] = "idle"
            await msg.reply_text(
                f"Ты выбрал класс {choice}.\n"
                f"Способность: {ability_description(choice)}\n"
                f"Удачи в приключениях!",
                reply_markup=MAIN_KB
            )
        else:
            await msg.reply_text("Пожалуйста, выбери класс из предложенных кнопок.", reply_markup=CLASS_KB)
        return

    # Главное меню
    if msg.text == "📊 Статус":
        await status_cmd(update, context)
    elif msg.text == "🎒 Инвентарь":
        await inventory_cmd(update, context)
    elif msg.text == "🗺️ Приключение":
        # Проверка кулдауна
        last_adventure = context.user_data.get("last_adventure")
        if last_adventure:
            cooldown = 30  # 30 секунд кулдауна
            elapsed = (datetime.now() - last_adventure).total_seconds()
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                await msg.reply_text(
                    f"Ты устал 😥 и не готов к новым приключениям 🗺️. Отдохни ещё {remaining} секунд .",
                    reply_markup=MAIN_KB
                )
                return
        await adventure_cmd(update, context)
    elif msg.text == "🧾 Квесты":
        await quests_cmd(update, context)
    elif msg.text == "🛒 Магазин":
        await shop_cmd(update, context)
    elif msg.text == "⚙️ Помощь":
        await help_cmd(update, context)
    else:
        # Игнор или подсказка
        await msg.reply_text("Не понимаю. Используй кнопки или команды /help.", reply_markup=MAIN_KB)

# --------------------------------- Main --------------------------------------

def main():
    load_players()
    app = ApplicationBuilder().token("").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("use_potion", use_potion_cmd))
    app.add_handler(CommandHandler("adventure", adventure_cmd))
    app.add_handler(CommandHandler("quests", quests_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))

    app.add_handler(CallbackQueryHandler(battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
