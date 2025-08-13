# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
import os
import random
from typing import Dict, Any, Optional, List

from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

DATA_FILE = "game_data.json"

# Хранилище игроков: key = str(user_id), value = dict
players: Dict[str, Dict[str, Any]] = {}

# Хранилище кланов: key = str(clan_name), value = dict
clans: Dict[str, Dict[str, Any]] = {}

# Клавиатуры
CLASS_KB = ReplyKeyboardMarkup(
    [["⚔️ Воин", "🧙 Маг", "🕵️ Вор"]],
    one_time_keyboard=True,
    resize_keyboard=True
)
MAIN_KB = ReplyKeyboardMarkup(
    [["🗺️ Приключение", "📊 Статус"], 
     ["🎒 Инвентарь", "🧾 Квесты"], 
     ["🛒 Магазин", "🎰 Казино"],
     ["🏆 Достижения", "🎁 Ежедневные"],
     ["⚔️ PvP", "🏰 Кланы"],
     ["🐾 Питомцы", "💼 Бизнес"],
     ["💸 Траты", "⚙️ Помощь"]],
    resize_keyboard=True
)

# ----------------------------- Безопасные помощники редактирования сообщений -----------------------------

async def safe_edit_message_text(query, text: str, parse_mode: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасно редактирует текст сообщения. Игнорирует ошибку 'Message is not modified'."""
    try:
        await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as exc:
        # Сообщение не менялось — просто игнорируем, чтобы не падать
        if "Message is not modified" in str(exc):
            return
        # Пробрасываем остальные ошибки
        raise

async def safe_edit_message_reply_markup(query, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасно редактирует inline-клавиатуру сообщения. Игнорирует ошибку 'Message is not modified'."""
    try:
        await query.edit_message_reply_markup(reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        raise

async def safe_edit_message_by_id(bot, chat_id: int, message_id: int, text: str, parse_mode: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Безопасно редактирует сообщение по chat_id/message_id, игнорируя 'Message is not modified'."""
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            return
        raise

# Базовые параметры классов
CLASS_STATS = {
    "⚔️ Воин": {"hp": 110, "attack": 7, "defense": 4, "ability": "Мощный удар", "color": "🛡️"},
    "🧙 Маг": {"hp": 95, "attack": 9, "defense": 2, "ability": "Огненная вспышка", "color": "🔮"},
    "🕵️ Вор": {"hp": 100, "attack": 7, "defense": 3, "ability": "Теневая атака", "color": "🗡️"},
}

# Расширенный магазин
SHOP_ITEMS = {
    "Малое зелье лечения": {"price": 15, "type": "consumable", "effect": {"heal": 35}, "emoji": "🧪"},
    "Большое зелье лечения": {"price": 35, "type": "consumable", "effect": {"heal": 70}, "emoji": "🔮"},
    "Руна силы": {"price": 30, "type": "consumable", "effect": {"attack_plus": 1}, "emoji": "⚡"},
    "Кожаная броня": {"price": 30, "type": "consumable", "effect": {"defense_plus": 1}, "emoji": "🛡️"},
    "Эликсир удачи": {"price": 50, "type": "consumable", "effect": {"luck_plus": 1}, "emoji": "🍀"},
    "Свиток телепортации": {"price": 25, "type": "consumable", "effect": {"escape": True}, "emoji": "📜"},
    "Амулет защиты": {"price": 100, "type": "equipment", "effect": {"defense_plus": 2}, "emoji": "🔮"},
    "Меч дракона": {"price": 200, "type": "equipment", "effect": {"attack_plus": 3}, "emoji": "⚔️"},
    # Питомцы в магазине
    "🐱 Кот": {"price": 150, "type": "pet", "pet_id": "cat", "emoji": "🐱"},
    "🐰 Кролик": {"price": 200, "type": "pet", "pet_id": "rabbit", "emoji": "🐰"},
    "🦉 Сова": {"price": 300, "type": "pet", "pet_id": "owl", "emoji": "🦉"},
    "🐺 Волк": {"price": 400, "type": "pet", "pet_id": "wolf", "emoji": "🐺"},
    "🦅 Феникс": {"price": 800, "type": "pet", "pet_id": "phoenix", "emoji": "🦅"},
    "🐉 Дракон": {"price": 1000, "type": "pet", "pet_id": "dragon", "emoji": "🐉"},
}

# Расширенные игры казино
CASINO_GAMES = {
    "double": {"name": "🎯 Удвоение", "multiplier": 2, "win_chance": 0.45, "min_bet": 5, "emoji": "🎯"},
    "dice": {"name": "🎲 Кости", "multiplier": 1.5, "win_chance": 0.5, "min_bet": 5, "emoji": "🎲"},
    "roulette": {"name": "🎡 Рулетка", "multiplier": 2, "win_chance": 0.4, "min_bet": 5, "emoji": "🎡"},
    "slots": {"name": "🎰 Слоты", "multiplier": 3, "win_chance": 0.3, "min_bet": 10, "emoji": "🎰"},
    "blackjack": {"name": "🃏 Блэкджек", "multiplier": 2.5, "win_chance": 0.48, "min_bet": 8, "emoji": "🃏"},
}

# Система достижений
ACHIEVEMENTS = {
    "first_blood": {"name": "🩸 Первая кровь", "desc": "Победите первого врага", "reward": {"gold": 20, "xp": 50}},
    "casino_king": {"name": "👑 Король казино", "desc": "Выиграйте 5 раз подряд", "reward": {"gold": 100, "xp": 200}},
    "rich_player": {"name": "💰 Богач", "desc": "Накопите 1000 золота", "reward": {"gold": 200, "xp": 300}},
    "level_master": {"name": "⭐ Мастер уровней", "desc": "Достигните 10 уровня", "reward": {"gold": 500, "xp": 1000}},
    "quest_hunter": {"name": "📜 Охотник за квестами", "desc": "Выполните 10 квестов", "reward": {"gold": 300, "xp": 400}},
    "pvp_champion": {"name": "🏆 Чемпион PvP", "desc": "Победите 20 игроков", "reward": {"gold": 400, "xp": 500}},
    "pet_lover": {"name": "🐾 Любитель питомцев", "desc": "Получите 3 питомца", "reward": {"gold": 150, "xp": 200}},
    "clan_leader": {"name": "🏰 Лидер клана", "desc": "Создайте клан", "reward": {"gold": 250, "xp": 300}},
    "business_tycoon": {"name": "🏢 Бизнес-магнат", "desc": "Владейте 3 бизнесами", "reward": {"gold": 300, "xp": 400}},
    "daily_master": {"name": "📅 Мастер ежедневных", "desc": "Получите 7 ежедневных наград подряд", "reward": {"gold": 400, "xp": 600}},
    "casino_professional": {"name": "🎰 Профессионал казино", "desc": "Выиграйте 50 игр в казино", "reward": {"gold": 500, "xp": 800}},
    "inventory_collector": {"name": "🎒 Коллекционер", "desc": "Соберите 10 разных предметов", "reward": {"gold": 200, "xp": 300}},
}

# Система питомцев
PETS = {
    "dragon": {"name": "🐉 Дракон", "bonus": {"attack": 5, "defense": 3}, "rarity": "legendary", "emoji": "🐉"},
    "phoenix": {"name": "🦅 Феникс", "bonus": {"hp": 50, "heal": 10}, "rarity": "legendary", "emoji": "🦅"},
    "wolf": {"name": "🐺 Волк", "bonus": {"attack": 3, "speed": 2}, "rarity": "rare", "emoji": "🐺"},
    "cat": {"name": "🐱 Кот", "bonus": {"luck": 2, "gold": 5}, "rarity": "common", "emoji": "🐱"},
    "owl": {"name": "🦉 Сова", "bonus": {"xp": 10, "wisdom": 1}, "rarity": "rare", "emoji": "🦉"},
    "rabbit": {"name": "🐰 Кролик", "bonus": {"speed": 3, "escape": 1}, "rarity": "common", "emoji": "🐰"},
}

# Бизнесы
BUSINESSES = {
    "stall": {"name": "🧺 Ларёк", "price": 50, "income_per_min": 2},
    "shop": {"name": "🏪 Магазин", "price": 800, "income_per_min": 6},
    "farm": {"name": "🌾 Ферма", "price": 1500, "income_per_min": 12},
    "mine": {"name": "⛏️ Шахта", "price": 3000, "income_per_min": 25},
}

# Ежедневные награды
DAILY_REWARDS = {
    1: {"gold": 10, "xp": 20, "item": "Малое зелье лечения"},
    2: {"gold": 15, "xp": 25, "item": "Руна силы"},
    3: {"gold": 20, "xp": 30, "item": "Кожаная броня"},
    4: {"gold": 25, "xp": 35, "item": "Малое зелье лечения"},
    5: {"gold": 30, "xp": 40, "item": "Эликсир удачи"},
    6: {"gold": 35, "xp": 45, "item": "Свиток телепортации"},
    7: {"gold": 50, "xp": 60, "item": "Большое зелье лечения"},
}

# Кланы
clans: Dict[str, Dict[str, Any]] = {}

# PvP система
pvp_requests: Dict[str, Dict[str, Any]] = {}
# Активные дуэли: key = duel_id, value = состояние дуэли
active_duels: Dict[str, Dict[str, Any]] = {}
# Быстрый маппинг игрока к его дуэли (чтобы не было нескольких боёв одновременно)
user_to_duel: Dict[str, str] = {}

# Система квестов
QUESTS = {
    "rat_hunter": {
        "title": "Крысолов",
        "desc": "Убей 3 крыс в окрестностях.",
        "target_type": "rat",
        "required": 3,
        "reward": {"xp": 100, "gold": 30, "item": "Малое зелье лечения"},
    },
    "goblin_slayer": {
        "title": "Истребитель гоблинов",
        "desc": "Победите 5 гоблинов.",
        "target_type": "goblin",
        "required": 5,
        "reward": {"xp": 150, "gold": 50, "item": "Руна силы"},
    },
    "wolf_hunter": {
        "title": "Охотник на волков",
        "desc": "Убейте 4 волка.",
        "target_type": "wolf",
        "required": 4,
        "reward": {"xp": 200, "gold": 75, "item": "Кожаная броня"},
    },
    "casino_regular": {
        "title": "Завсегдатай казино",
        "desc": "Сыграйте 10 раз в казино.",
        "target_type": "casino_plays",
        "required": 10,
        "reward": {"xp": 120, "gold": 100, "item": "Эликсир удачи"},
    },
    "business_owner": {
        "title": "Владелец бизнеса",
        "desc": "Купите 2 бизнеса.",
        "target_type": "businesses_owned",
        "required": 2,
        "reward": {"xp": 180, "gold": 150, "item": "Амулет защиты"},
    },
}

def generate_random_quest(player_level: int) -> Dict[str, Any]:
    """Генерирует случайный квест на основе уровня игрока"""
    quest_templates = [
        {
            "title": "Сборщик ресурсов",
            "desc": "Найдите {amount} предметов в приключениях.",
            "target_type": "items_found",
            "required": lambda level: random.randint(3, 5 + level // 2),
            "reward": lambda level: {"xp": 50 + level * 10, "gold": 20 + level * 5, "item": "Малое зелье лечения"}
        },
        {
            "title": "Истребитель монстров",
            "desc": "Победите {amount} врагов любого типа.",
            "target_type": "enemies_killed",
            "required": lambda level: random.randint(5, 8 + level),
            "reward": lambda level: {"xp": 80 + level * 15, "gold": 30 + level * 8, "item": "Руна силы"}
        },
        {
            "title": "Золотоискатель",
            "desc": "Заработайте {amount} золота.",
            "target_type": "gold_earned",
            "required": lambda level: random.randint(50, 100 + level * 20),
            "reward": lambda level: {"xp": 60 + level * 12, "gold": 40 + level * 10, "item": "Эликсир удачи"}
        }
    ]
    
    template = random.choice(quest_templates)
    required = template["required"](player_level)
    reward = template["reward"](player_level)
    
    return {
        "title": template["title"],
        "desc": template["desc"].format(amount=required),
        "target_type": template["target_type"],
        "required": required,
        "reward": reward
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
    
    # Миграция существующих данных игроков
    migrate_player_data()

def migrate_player_data() -> None:
    """Мигрирует данные существующих игроков для совместимости с новыми полями"""
    for player_id, player in players.items():
        # Добавляем отсутствующие поля
        if "pets" not in player:
            player["pets"] = []
        if "achievements" not in player:
            player["achievements"] = {}
        if "clan" not in player:
            player["clan"] = None
        if "daily_streak" not in player:
            player["daily_streak"] = 0
        if "last_daily_reward" not in player:
            player["last_daily_reward"] = None
        if "pvp_wins" not in player:
            player["pvp_wins"] = 0
        if "pvp_losses" not in player:
            player["pvp_losses"] = 0
        if "luck" not in player:
            player["luck"] = 0
        if "equipment" not in player:
            player["equipment"] = {}
        if "businesses" not in player:
            player["businesses"] = {}
        if "last_business_claim" not in player:
            player["last_business_claim"] = None
    
    # Сохраняем обновленные данные
    save_players()

def save_players() -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(players, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def save_clans() -> None:
    try:
        with open("clans_data.json", "w", encoding="utf-8") as f:
            json.dump(clans, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_clans() -> None:
    global clans
    if os.path.exists("clans_data.json"):
        try:
            with open("clans_data.json", "r", encoding="utf-8") as f:
                clans = json.load(f)
        except Exception:
            clans = {}
    else:
        clans = {}

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
            "gold": 50,  # Увеличим стартовое золото
            "inventory": {"Малое зелье лечения": 2},
            "quests": {},
            "last_casino_play": None,
            "achievements": {},
            "pets": [],
            "clan": None,
            "daily_reward_claimed": False,
            "last_daily_reward": None,
            "pvp_wins": 0,
            "pvp_losses": 0,
            "luck": 0,
            "equipment": {},
        }
        save_players()
    return players[uid]

def check_achievements(player: Dict[str, Any], action: str, value: Any = None) -> List[str]:
    """Проверяет и выдает достижения"""
    earned = []
    
    if action == "first_kill" and "first_blood" not in player["achievements"]:
        player["achievements"]["first_blood"] = {"earned": True, "date": datetime.now().isoformat()}
        earned.append("first_blood")
    
    elif action == "casino_win" and "casino_king" not in player["achievements"]:
        # Проверяем 5 побед подряд
        wins = player.get("casino_wins_streak", 0) + 1
        player["casino_wins_streak"] = wins
        if wins >= 5:
            player["achievements"]["casino_king"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("casino_king")
    
    elif action == "gold_check" and "rich_player" not in player["achievements"]:
        if player["gold"] >= 1000:
            player["achievements"]["rich_player"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("rich_player")
    
    elif action == "level_check" and "level_master" not in player["achievements"]:
        if player["level"] >= 10:
            player["achievements"]["level_master"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("level_master")
    
    elif action == "quest_complete" and "quest_hunter" not in player["achievements"]:
        completed_quests = sum(1 for q in player["quests"].values() if q.get("status") == "completed")
        if completed_quests >= 10:
            player["achievements"]["quest_hunter"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("quest_hunter")
    
    elif action == "pvp_win" and "pvp_champion" not in player["achievements"]:
        if player["pvp_wins"] >= 20:
            player["achievements"]["pvp_champion"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("pvp_champion")
    
    elif action == "pet_obtained" and "pet_lover" not in player["achievements"]:
        if len(player["pets"]) >= 3:
            player["achievements"]["pet_lover"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("pet_lover")
    
    elif action == "pet_check" and "pet_lover" not in player["achievements"]:
        if len(player["pets"]) >= 3:
            player["achievements"]["pet_lover"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("pet_lover")
    
    elif action == "clan_created" and "clan_leader" not in player["achievements"]:
        player["achievements"]["clan_leader"] = {"earned": True, "date": datetime.now().isoformat()}
        earned.append("clan_leader")
    
    # Новые достижения
    elif action == "business_check" and "business_tycoon" not in player["achievements"]:
        if len(player.get("businesses", {})) >= 3:
            player["achievements"]["business_tycoon"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("business_tycoon")
    
    elif action == "daily_check" and "daily_master" not in player["achievements"]:
        if player.get("daily_streak", 0) >= 7:
            player["achievements"]["daily_master"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("daily_master")
    
    elif action == "casino_total_wins" and "casino_professional" not in player["achievements"]:
        total_wins = player.get("casino_total_wins", 0) + 1
        player["casino_total_wins"] = total_wins
        if total_wins >= 50:
            player["achievements"]["casino_professional"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("casino_professional")
    
    elif action == "inventory_check" and "inventory_collector" not in player["achievements"]:
        unique_items = len(player.get("inventory", {}))
        if unique_items >= 10:
            player["achievements"]["inventory_collector"] = {"earned": True, "date": datetime.now().isoformat()}
            earned.append("inventory_collector")
    
    if earned:
        save_players()
    
    return earned

def grant_achievement_rewards(player: Dict[str, Any], achievement_id: str) -> str:
    """Выдает награды за достижение"""
    if achievement_id in ACHIEVEMENTS:
        reward = ACHIEVEMENTS[achievement_id]["reward"]
        player["gold"] += reward.get("gold", 0)
        player["xp"] += reward.get("xp", 0)
        if "item" in reward:
            add_item(player, reward["item"], 1)
        save_players()
        return f"🏆 +{reward.get('gold', 0)}💰 +{reward.get('xp', 0)}XP"
    return ""

def get_pet_bonuses(player: Dict[str, Any]) -> Dict[str, int]:
    """Получает бонусы от питомцев"""
    bonuses = {"attack": 0, "defense": 0, "hp": 0, "luck": 0, "gold": 0, "xp": 0}
    
    pets = player.get("pets", [])
    for pet_id in pets:
        if pet_id in PETS:
            pet = PETS[pet_id]
            for stat, bonus in pet["bonus"].items():
                bonuses[stat] = bonuses.get(stat, 0) + bonus
    
    return bonuses

def get_player_stats_with_pets(player: Dict[str, Any]) -> Dict[str, int]:
    """Получает характеристики игрока с учетом бонусов питомцев"""
    bonuses = get_pet_bonuses(player)
    
    stats = {
        "attack": player["attack"] + bonuses["attack"],
        "defense": player["defense"] + bonuses["defense"],
        "hp": player["hp"],
        "max_hp": player["max_hp"] + bonuses["hp"],
        "luck": player.get("luck", 0) + bonuses["luck"]
    }
    
    return stats

def can_claim_daily_reward(player: Dict[str, Any]) -> bool:
    """Проверяет, может ли игрок получить ежедневную награду"""
    if not player.get("last_daily_reward"):
        return True
    
    last_claim = datetime.fromisoformat(player["last_daily_reward"])
    now = datetime.now()
    
    # Проверяем, прошло ли 24 часа
    return (now - last_claim).total_seconds() >= 86400

def get_daily_streak(player: Dict[str, Any]) -> int:
    """Получает текущую серию ежедневных наград"""
    return player.get("daily_streak", 0)

def claim_daily_reward(player: Dict[str, Any]) -> Dict[str, Any]:
    """Выдает ежедневную награду"""
    if not can_claim_daily_reward(player):
        return {"success": False, "message": "⏳ Подождите до завтра!"}
    
    streak = get_daily_streak(player) + 1
    if streak > 7:
        streak = 1  # Сбрасываем на первую награду
    
    reward = DAILY_REWARDS.get(streak, DAILY_REWARDS[1])
    
    player["gold"] += reward["gold"]
    player["xp"] += reward["xp"]
    player["daily_streak"] = streak
    player["last_daily_reward"] = datetime.now().isoformat()
    
    if "item" in reward:
        add_item(player, reward["item"], 1)
    
    # Проверяем достижения
    check_achievements(player, "daily_check")
    check_achievements(player, "inventory_check")
    
    save_players()
    
    return {
        "success": True,
        "message": f"🎁 День {streak}/7: +{reward['gold']}💰 +{reward['xp']}XP +{reward['item']}",
        "streak": streak,
        "reward": reward
    }

def create_clan(clan_name: str, leader_id: str, leader_name: str) -> bool:
    """Создает новый клан"""
    if clan_name in clans:
        return False
    
    clans[clan_name] = {
        "name": clan_name,
        "leader": leader_id,
        "members": [leader_id],
        "level": 1,
        "xp": 0,
        "created": datetime.now().isoformat(),
        "description": f"Клан {clan_name}",
        "color": random.choice(["🔴", "🔵", "🟢", "🟡", "🟣", "🟠"])
    }
    
    # Добавляем игрока в клан
    players[leader_id]["clan"] = clan_name
    
    save_players()
    save_clans()
    return True

def join_clan(clan_name: str, player_id: str) -> bool:
    """Добавляет игрока в клан"""
    if clan_name not in clans:
        return False
    
    clan = clans[clan_name]
    if player_id in clan["members"]:
        return False
    
    if len(clan["members"]) >= 20:  # Максимум 20 участников
        return False
    
    clan["members"].append(player_id)
    players[player_id]["clan"] = clan_name
    
    save_players()
    save_clans()
    return True

def leave_clan(player_id: str) -> bool:
    """Покидает клан"""
    if player_id not in players:
        return False
    
    player = players[player_id]
    if not player.get("clan"):
        return False
    
    clan_name = player["clan"]
    if clan_name in clans:
        clan = clans[clan_name]
        if player_id in clan["members"]:
            clan["members"].remove(player_id)
            
            # Если лидер покидает клан, назначаем нового лидера
            if clan["leader"] == player_id and clan["members"]:
                clan["leader"] = clan["members"][0]
            elif not clan["members"]:
                # Удаляем пустой клан
                del clans[clan_name]
    
    player["clan"] = None
    save_players()
    save_clans()
    return True

def send_pvp_request(from_id: str, to_id: str) -> bool:
    """Отправляет запрос на PvP"""
    if from_id == to_id:
        return False
    
    if from_id not in players or to_id not in players:
        return False
    
    request_id = f"{from_id}_{to_id}"
    if request_id in pvp_requests:
        return False
    
    pvp_requests[request_id] = {
        "from_id": from_id,
        "to_id": to_id,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    return True

def accept_pvp_request(request_id: str) -> bool:
    """Принимает запрос на PvP"""
    if request_id not in pvp_requests:
        return False
    
    request = pvp_requests[request_id]
    if request["status"] != "pending":
        return False
    
    request["status"] = "accepted"
    return True

def decline_pvp_request(request_id: str) -> bool:
    """Отклоняет запрос на PvP"""
    if request_id not in pvp_requests:
        return False
    
    del pvp_requests[request_id]
    return True

def set_class(player: Dict[str, Any], class_name: str) -> None:
    stats = CLASS_STATS[class_name]
    player["class"] = class_name
    player["max_hp"] = stats["hp"]
    player["hp"] = stats["hp"]
    player["attack"] = stats["attack"]
    player["defense"] = stats["defense"]
    
    # Бонусы питомцев будут применяться при отображении статуса
    
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
    
    # Проверяем достижения
    check_achievements(player, "level_check")
    check_achievements(player, "gold_check")
    
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
    
    # Проверяем достижения
    earned_achievements = []
    earned_achievements.extend(check_achievements(player, "first_kill"))
    earned_achievements.extend(check_achievements(player, "gold_check"))
    earned_achievements.extend(check_achievements(player, "level_check"))
    
    level_up_text = check_level_up(player)
    
    # Выдаем награды за достижения
    achievement_text = ""
    for achievement_id in earned_achievements:
        reward_text = grant_achievement_rewards(player, achievement_id)
        achievement_text += f"\n🏆 {ACHIEVEMENTS[achievement_id]['name']}: {reward_text}"
    
    save_players()
    return f"+{xp} XP, +{gold} золота.{loot_text}{level_up_text}{achievement_text}"

def update_quests_on_enemy_kill(player: Dict[str, Any], enemy_type: str) -> str:
    """Обновляет прогресс всех подходящих активных квестов при убийстве врага.
    Возвращает текст с сообщениями о прогрессе/выполнении."""
    if not player or "quests" not in player:
        return ""

    updates: List[str] = []
    changed: bool = False

    for quest in player["quests"].values():
        if quest.get("status") != "active":
            continue

        target_type = quest.get("target_type")
        if target_type in (enemy_type, "enemies_killed"):
            # Инкремент прогресса
            quest["progress"] = int(quest.get("progress", 0)) + 1
            changed = True

            # Проверяем завершение
            required = int(quest.get("required", 0))
            if required and quest["progress"] >= required:
                quest["status"] = "completed"
                rew = quest.get("reward", {})
                add_text = grant_rewards(
                    player,
                    int(rew.get("xp", 0)),
                    int(rew.get("gold", 0)),
                    rew.get("item")
                )
                # Достижение за квесты
                check_achievements(player, "quest_complete")
                updates.append(f"\n✅ Квест '{quest.get('title', 'Без названия')}' выполнен! {add_text}")
            else:
                updates.append(
                    f"\nКвест '{quest.get('title', 'Без названия')}': прогресс {quest.get('progress', 0)}/{quest.get('required', 0)}."
                )

    if changed:
        save_players()

    return "".join(updates)

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
        "attack": base["attack"] + scale * 2,  # Увеличиваем атаку сильнее
        "defense": base["defense"] + (scale // 2),
        "xp": base["xp"] + 10 * scale,
        "gold": random.randint(*base["gold"]) + 2 * scale,
        "loot": random.choice(base["loot"]),
    }
    return enemy

def dmg_roll(atk: int, df: int, spread: int = 2) -> int:
    # Урон теперь зависит от разницы между атакой и защитой
    raw = atk + random.randint(0, spread) - max(0, df - 2)  # Защита уменьшает урон, но не более чем на 2
    return max(1, raw)

def ability_description(class_name: str) -> str:
    if class_name == "⚔️ Воин":
        return "Мощный удар: нанесение двойного урона один раз за бой."
    if class_name == "🧙 Маг":
        return "Огненная вспышка: 15 чистого урона один раз за бой."
    if class_name == "🕵️ Вор":
        return "Теневая атака: удар, игнорирующий защиту, один раз за бой."
    return ""

def build_battle_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗡️ Атака", callback_data="battle:attack"),
         InlineKeyboardButton("✨ Способность", callback_data="battle:ability")],
        [InlineKeyboardButton("🧪 Зелье", callback_data="battle:potion"),
         InlineKeyboardButton("🏃 Бег", callback_data="battle:run")],
    ])

def build_shop_kb(player: Dict[str, Any] = None) -> InlineKeyboardMarkup:
    """Улучшенная клавиатура магазина с массовой покупкой"""
    buttons = []
    
    # Группируем предметы по типам
    consumables = []
    equipment = []
    pets = []
    
    for item_name, meta in SHOP_ITEMS.items():
        emoji = meta.get("emoji", "📦")
        price = meta['price']
        item_type = meta["type"]
        
        # Показываем количество в инвентаре
        inventory_count = 0
        if player:
            inventory_count = player["inventory"].get(item_name, 0)
        
        if item_type == "consumable":
            consumables.append((item_name, meta, inventory_count))
        elif item_type == "equipment":
            equipment.append((item_name, meta, inventory_count))
        elif item_type == "pet":
            pets.append((item_name, meta, inventory_count))
    
    # Потребляемые предметы
    if consumables:
        buttons.append([InlineKeyboardButton("🧪 Потребляемые предметы", callback_data="shop:category:consumable")])
        for item_name, meta, count in consumables:
            emoji = meta.get("emoji", "📦")
            price = meta['price']
            buttons.append([InlineKeyboardButton(
                f"{emoji} {item_name} ({price}💰) x{count}",
                callback_data=f"shop:buy:{item_name}"
            )])
    
    # Экипировка
    if equipment:
        buttons.append([InlineKeyboardButton("⚔️ Экипировка", callback_data="shop:category:equipment")])
        for item_name, meta, count in equipment:
            emoji = meta.get("emoji", "📦")
            price = meta['price']
            buttons.append([InlineKeyboardButton(
                f"{emoji} {item_name} ({price}💰) x{count}",
                callback_data=f"shop:buy:{item_name}"
            )])
    
    # Питомцы
    if pets:
        buttons.append([InlineKeyboardButton("🐾 Питомцы", callback_data="shop:category:pet")])
        for item_name, meta, count in pets:
            emoji = meta.get("emoji", "📦")
            price = meta['price']
            pet_id = meta["pet_id"]
            
            if player and pet_id in player.get("pets", []):
                buttons.append([InlineKeyboardButton(f"{emoji} {item_name} ✅ (Уже есть)", callback_data="shop:already_owned")])
            else:
                buttons.append([InlineKeyboardButton(f"{emoji} {item_name} ({price}💰)", callback_data=f"shop:buy:{item_name}")])
    
    # Кнопки массовой покупки
    buttons.append([InlineKeyboardButton("🛒 Массовая покупка", callback_data="shop:bulk")])
    buttons.append([InlineKeyboardButton("💰 Баланс", callback_data="shop:balance")])
    buttons.append([InlineKeyboardButton("Закрыть", callback_data="shop:close")])
    
    return InlineKeyboardMarkup(buttons)

def build_bulk_shop_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура для массовой покупки"""
    buttons = []
    
    # Только потребляемые предметы для массовой покупки
    for item_name, meta in SHOP_ITEMS.items():
        if meta["type"] == "consumable":
            emoji = meta.get("emoji", "📦")
            price = meta['price']
            inventory_count = player["inventory"].get(item_name, 0)
            
            buttons.append([InlineKeyboardButton(
                f"{emoji} {item_name} x{inventory_count}",
                callback_data=f"shop:bulk:{item_name}"
            )])
    
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="shop:back")])
    return InlineKeyboardMarkup(buttons)

def get_business_income_info(player: Dict[str, Any]) -> Dict[str, Any]:
    """Получает информацию о доходе от бизнесов"""
    owned = player.get("businesses", {})
    total_income_per_min = 0
    total_income_per_hour = 0
    business_details = []
    
    for biz_id, meta in owned.items():
        if biz_id in BUSINESSES:
            base_income = BUSINESSES[biz_id]["income_per_min"]
            level = meta.get("level", 1)
            income_per_min = base_income * level
            income_per_hour = income_per_min * 60
            
            total_income_per_min += income_per_min
            total_income_per_hour += income_per_hour
            
            business_details.append({
                "id": biz_id,
                "name": BUSINESSES[biz_id]["name"],
                "level": level,
                "income_per_min": income_per_min,
                "income_per_hour": income_per_hour,
                "upgrade_cost": int(BUSINESSES[biz_id]["price"] * 0.5)
            })
    
    return {
        "total_per_min": total_income_per_min,
        "total_per_hour": total_income_per_hour,
        "businesses": business_details
    }

def get_time_until_next_daily(player: Dict[str, Any]) -> str:
    """Возвращает время до следующей ежедневной награды"""
    if not player.get("last_daily_reward"):
        return "Доступно сейчас!"
    
    last_claim = datetime.fromisoformat(player["last_daily_reward"])
    now = datetime.now()
    time_diff = timedelta(hours=24) - (now - last_claim)
    
    if time_diff.total_seconds() <= 0:
        return "Доступно сейчас!"
    
    hours = int(time_diff.total_seconds() // 3600)
    minutes = int((time_diff.total_seconds() % 3600) // 60)
    
    if hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"

def build_businesses_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Улучшенная клавиатура бизнесов с детальной информацией"""
    buttons = []
    owned = player.get("businesses", {})
    income_info = get_business_income_info(player)
    
    # Заголовок с общей информацией
    total_income = income_info["total_per_min"]
    buttons.append([InlineKeyboardButton(
        f"💰 Общий доход: {total_income}/мин ({income_info['total_per_hour']}/час)",
        callback_data="biz:info"
    )])
    
    # Доступные для покупки бизнесы
    for biz_id, meta in BUSINESSES.items():
        name = meta["name"]
        price = meta["price"]
        income = meta["income_per_min"]
        
        if biz_id in owned:
            level = owned[biz_id].get("level", 1)
            current_income = income * level
            upgrade_cost = int(price * 0.5)
            buttons.append([InlineKeyboardButton(
                f"{name} ✅ ур.{level} ({current_income}/мин) 💰{upgrade_cost}",
                callback_data=f"biz:upgrade:{biz_id}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                f"{name} — {price}💰 ({income}/мин)",
                callback_data=f"biz:buy:{biz_id}"
            )])
    
    # Кнопки управления
    buttons.append([InlineKeyboardButton("📥 Забрать доход", callback_data="biz:claim")])
    buttons.append([InlineKeyboardButton("➕ Улучшить все (x2 доход)", callback_data="biz:upgrade_all")])
    buttons.append([InlineKeyboardButton("📊 Детали", callback_data="biz:details")])
    buttons.append([InlineKeyboardButton("🚪 Закрыть", callback_data="biz:close")])
    
    return InlineKeyboardMarkup(buttons)

def battle_text(player: Dict[str, Any], enemy: Dict[str, Any], log: str = "") -> str:
    # Получаем характеристики с учетом бонусов питомцев
    stats_with_pets = get_player_stats_with_pets(player)
    
    return (
        f"⚔️ Бой: {enemy['name']}\n"
        f"Враг HP: {enemy['hp']}/{enemy['max_hp']}\n"
        f"Ты HP: {stats_with_pets['hp']}/{stats_with_pets['max_hp']}\n"
        f"Атака/Защита: {stats_with_pets['attack']}/{stats_with_pets['defense']}\n\n"
        f"{log}"
    )

def build_casino_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    buttons = []
    for game_type, game in CASINO_GAMES.items():
        can_play = player["gold"] >= game["min_bet"]
        text = f"{game['name']} (от {game['min_bet']}💰)" if can_play else f"{game['name']} ❌"
        callback = f"casino:{game_type}" if can_play else "casino:no_money"
        buttons.append([InlineKeyboardButton(text, callback_data=callback)])
    buttons.append([InlineKeyboardButton("💰 Баланс", callback_data="casino:balance")])
    buttons.append([InlineKeyboardButton("🚪 Выход", callback_data="casino:exit")])
    return InlineKeyboardMarkup(buttons)

def build_casino_games_kb() -> InlineKeyboardMarkup:
    """Улучшенная клавиатура с играми казино и быстрыми ставками"""
    keyboard = []
    
    # Быстрые ставки
    keyboard.append([InlineKeyboardButton("⚡ Быстрые ставки", callback_data="casino:quick_bets")])
    
    # Игры
    for game_id, game_info in CASINO_GAMES.items():
        keyboard.append([InlineKeyboardButton(
            f"{game_info['emoji']} {game_info['name']} ({int(game_info['win_chance'] * 100)}% | x{game_info['multiplier']})",
            callback_data=f"casino:{game_id}"
        )])
    
    # Кнопки управления
    keyboard.append([
        InlineKeyboardButton("💰 Баланс", callback_data="casino:balance"),
        InlineKeyboardButton("💸 Изменить ставку", callback_data="casino:change_bet")
    ])
    keyboard.append([
        InlineKeyboardButton("📊 История", callback_data="casino:history"),
        InlineKeyboardButton("🚪 Выйти", callback_data="casino:exit")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def build_quick_bets_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура быстрых ставок"""
    balance = player["gold"]
    keyboard = []
    
    # Процентные ставки
    percentages = [10, 25, 50, 75, 100]
    for percent in percentages:
        bet_amount = int(balance * percent / 100)
        if bet_amount >= 5:  # Минимальная ставка
            keyboard.append([InlineKeyboardButton(
                f"{percent}% = {bet_amount}💰",
                callback_data=f"casino:quick_bet:{bet_amount}"
            )])
    
    # Фиксированные ставки
    fixed_bets = [10, 25, 50, 100, 250, 500]
    for bet in fixed_bets:
        if bet <= balance:
            keyboard.append([InlineKeyboardButton(
                f"{bet}💰",
                callback_data=f"casino:quick_bet:{bet}"
            )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="casino:back")])
    return InlineKeyboardMarkup(keyboard)

def add_casino_history(player: Dict[str, Any], game_type: str, bet: int, result: bool, prize: int = 0):
    """Добавляет запись в историю казино"""
    if "casino_history" not in player:
        player["casino_history"] = []
    
    history_entry = {
        "game": game_type,
        "bet": bet,
        "result": result,
        "prize": prize,
        "timestamp": datetime.now().isoformat()
    }
    
    player["casino_history"].append(history_entry)
    
    # Ограничиваем историю последними 20 играми
    if len(player["casino_history"]) > 20:
        player["casino_history"] = player["casino_history"][-20:]
    
    save_players()

def get_casino_stats(player: Dict[str, Any]) -> Dict[str, Any]:
    """Получает статистику казино"""
    history = player.get("casino_history", [])
    
    if not history:
        return {"total_games": 0, "wins": 0, "losses": 0, "winrate": 0, "total_profit": 0}
    
    wins = sum(1 for entry in history if entry["result"])
    losses = len(history) - wins
    total_profit = sum(entry["prize"] - entry["bet"] for entry in history)
    winrate = (wins / len(history)) * 100 if history else 0
    
    return {
        "total_games": len(history),
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "total_profit": total_profit
    }

def play_casino_game(player: Dict[str, Any], game_type: str, bet: int) -> Dict[str, Any]:
    """Основная логика игры в казино"""
    game = CASINO_GAMES[game_type]
    
    if bet < game["min_bet"]:
        return {"success": False, "message": f"❌ Минимальная ставка: {game['min_bet']} золота"}
    
    if player["gold"] < bet:
        return {"success": False, "message": "❌ Недостаточно золота!"}
    
    # Проверка кулдауна (раз в 30 секунд)
    last_play = player.get("last_casino_play")
    if last_play:
        last_play = datetime.fromisoformat(last_play)
        elapsed = (datetime.now() - last_play).total_seconds()
        if elapsed < 30:
            return {"success": False, "message": f"⏳ Подождите {int(30 - elapsed)} секунд перед следующей игрой"}
    
    player["gold"] -= bet
    player["last_casino_play"] = datetime.now().isoformat()
    
    # Логика игр
    if game_type == "double":
        if random.random() < game["win_chance"]:
            prize = bet * game["multiplier"]
            player["gold"] += prize
            # Проверяем достижения
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🎉 Победа! Выиграли {prize} золота!", "prize": prize}
        return {"success": False, "message": f"💸 Проигрыш! Потеряли {bet} золота."}
    
    elif game_type == "dice":
        player_roll = random.randint(1, 6)
        casino_roll = random.randint(1, 6)
        if player_roll > casino_roll:
            prize = int(bet * game["multiplier"])
            player["gold"] += prize
            # Проверяем достижения
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🎲 Вы: {player_roll} | Казино: {casino_roll}\n🏆 Выиграли {prize} золота!"}
        elif player_roll == casino_roll:
            player["gold"] += bet
            return {"success": None, "message": f"🎲 Вы: {player_roll} | Казино: {casino_roll}\n🤝 Ничья! Ставка возвращена."}
        else:
            return {"success": False, "message": f"🎲 Вы: {player_roll} | Казино: {casino_roll}\n💸 Проиграли {bet} золота."}
    
    elif game_type == "roulette":
        number = random.randint(0, 36)
        color = "🔴" if number % 2 == 1 else "⚫" if number != 0 else "🟢"
        if number == 0:
            return {"success": False, "message": f"🎡 Выпало: {color}0\n💸 Проиграли {bet} золота!"}
        elif (color == "🔴" and random.random() < game["win_chance"]) or (color == "⚫" and random.random() < game["win_chance"]):
            prize = bet * game["multiplier"]
            player["gold"] += prize
            # Проверяем достижения
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🎡 Выпало: {color}{number}\n🎉 Выиграли {prize} золота!"}
        else:
            return {"success": False, "message": f"🎡 Выпало: {color}{number}\n💸 Проиграли {bet} золота."}
    
    elif game_type == "slots":
        symbols = ["🍎", "🍊", "🍇", "🍒", "💎", "7️⃣"]
        result = [random.choice(symbols) for _ in range(3)]
        if len(set(result)) == 1:  # Все символы одинаковые
            prize = bet * game["multiplier"]
            player["gold"] += prize
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🎰 {' '.join(result)}\n🎉 ДЖЕКПОТ! Выиграли {prize} золота!"}
        else:
            return {"success": False, "message": f"🎰 {' '.join(result)}\n💸 Проиграли {bet} золота."}
    
    elif game_type == "blackjack":
        player_cards = [random.randint(1, 10) for _ in range(2)]
        dealer_cards = [random.randint(1, 10) for _ in range(2)]
        
        player_sum = sum(player_cards)
        dealer_sum = sum(dealer_cards)
        
        if player_sum == 21:
            prize = bet * game["multiplier"]
            player["gold"] += prize
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🃏 Блэкджек! Выиграли {prize} золота!"}
        elif player_sum > 21:
            return {"success": False, "message": f"🃏 Перебор! Проиграли {bet} золота."}
        elif dealer_sum > 21 or player_sum > dealer_sum:
            prize = int(bet * game["multiplier"])
            player["gold"] += prize
            check_achievements(player, "casino_win")
            check_achievements(player, "casino_total_wins")
            return {"success": True, "message": f"🃏 Победа! Выиграли {prize} золота!"}
        else:
            return {"success": False, "message": f"🃏 Проиграли {bet} золота."}
    
    save_players()
    return {"success": False, "message": "⚠️ Ошибка в игре"}

# ----------------------------- Хендлеры команд -------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Герой")

    if player["class"] is None:
        await update.message.reply_text(
            f"🎮 <b>Добро пожаловать в игру, {player['name']}!</b>\n\n"
            f"🌟 Выберите свой класс и начните приключение:\n\n"
            f"⚔️ <b>Воин</b> - Высокое HP и защита\n"
            f"🧙 <b>Маг</b> - Сильная атака и магия\n"
            f"🕵️ <b>Вор</b> - Сбалансированные характеристики\n\n"
            f"💡 Каждый класс имеет уникальную способность!",
            parse_mode="HTML",
            reply_markup=CLASS_KB
        )
        context.user_data["state"] = "choose_class"
    else:
        # Бонусы питомцев будут применяться при отображении статуса
        
        await update.message.reply_text(
            f"✨ <b>С возвращением, {player['name']}!</b>\n\n"
            f"🎭 Класс: {player['class']}\n"
            f"💫 Способность: {ability_description(player['class'])}\n"
            f"💰 Золото: {player['gold']}\n"
            f"⭐ Уровень: {player['level']}\n\n"
            f"🎮 Выбирай действие:",
            parse_mode="HTML",
            reply_markup=MAIN_KB
        )
        context.user_data["state"] = "idle"

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎮 <b>Доступные команды:</b>\n\n"
        "⚔️ <b>Основные:</b>\n"
        "/start - Начать игру\n"
        "/status - Показать статус\n"
        "/inventory - Открыть инвентарь\n\n"
        "🌍 <b>Игровые:</b>\n"
        "/adventure - Отправиться в приключение\n"
        "/quests - Активные квесты\n"
        "/shop - Посетить магазин\n"
        "/casino - Играть в казино\n\n"
        "🏆 <b>Новые функции:</b>\n"
        "/achievements - Достижения\n"
        "/daily - Ежедневные награды\n"
        "/pets - Питомцы\n"
        "/clans - Кланы\n"
        "/pvp - PvP бои\n\n"
        "🧪 <b>Предметы:</b>\n"
        "/use_potion - Использовать зелье\n\n"
        "🛠️ <b>Прочее:</b>\n"
        "/help - Показать это сообщение\n"
        "/spend - Другие способы тратить золото"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    
    # Получаем характеристики с учетом бонусов питомцев
    stats_with_pets = get_player_stats_with_pets(p)
    pet_bonuses = get_pet_bonuses(p)
    
    # Информация о бизнесах
    business_info = get_business_income_info(p)
    
    # Время до следующей ежедневной награды
    daily_timer = get_time_until_next_daily(p)
    
    text = (
        f"📊 <b>Статус {p['name']} ({p['class'] or 'Без класса'})</b>\n\n"
        f"⚔️ Уровень: <b>{p['level']}</b> ({p['xp']}/{get_xp_to_next(p['level'])} XP)\n"
        f"❤️ HP: <b>{stats_with_pets['hp']}/{stats_with_pets['max_hp']}</b>\n"
        f"🗡️ Атака: <b>{stats_with_pets['attack']}</b> 🛡️ Защита: <b>{stats_with_pets['defense']}</b>\n"
        f"💰 Золото: <b>{p['gold']}</b>\n"
        f"🍀 Удача: <b>{stats_with_pets['luck']}</b>\n\n"
    )
    
    # Информация о бизнесах
    if business_info["total_per_min"] > 0:
        text += f"💼 <b>Бизнесы:</b> {business_info['total_per_min']}/мин ({business_info['total_per_hour']}/час)\n"
        text += f"📦 Владений: {len(p.get('businesses', {}))}\n\n"
    
    # Ежедневные награды
    text += f"🎁 <b>Ежедневная награда:</b> {daily_timer}\n\n"
    
    # Бонусы питомцев
    if pet_bonuses["attack"] > 0 or pet_bonuses["defense"] > 0 or pet_bonuses["hp"] > 0:
        text += "🐾 <b>Бонусы питомцев:</b>\n"
        if pet_bonuses["attack"] > 0:
            text += f"🗡️ Атака +{pet_bonuses['attack']}\n"
        if pet_bonuses["defense"] > 0:
            text += f"🛡️ Защита +{pet_bonuses['defense']}\n"
        if pet_bonuses["hp"] > 0:
            text += f"❤️ HP +{pet_bonuses['hp']}\n"
        if pet_bonuses["luck"] > 0:
            text += f"🍀 Удача +{pet_bonuses['luck']}\n"
        text += "\n"
    
    # Клан
    if p.get("clan"):
        text += f"🏰 Клан: <b>{p['clan']}</b>\n\n"
    
    # PvP статистика
    if p.get("pvp_wins", 0) > 0 or p.get("pvp_losses", 0) > 0:
        wins = p.get("pvp_wins", 0)
        losses = p.get("pvp_losses", 0)
        total = wins + losses
        winrate = (wins / total * 100) if total > 0 else 0
        text += f"⚔️ PvP: {wins}W/{losses}L ({winrate:.1f}%)\n\n"
    
    # Способность
    text += f"✨ Способность: {ability_description(p['class']) if p['class'] else '-'}"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def achievements_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать достижения игрока"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    earned = p.get("achievements", {})
    
    # Поля уже инициализированы в migrate_player_data()
    
    if not earned:
        await update.message.reply_text(
            "🏆 <b>Достижения:</b>\n\n"
            "У вас пока нет достижений. Играйте больше!",
            parse_mode="HTML",
            reply_markup=MAIN_KB
        )
        return
    
    text = "🏆 <b>Ваши достижения:</b>\n\n"
    for achievement_id, data in earned.items():
        if achievement_id in ACHIEVEMENTS:
            achievement = ACHIEVEMENTS[achievement_id]
            date = datetime.fromisoformat(data["date"]).strftime("%d.%m.%Y")
            text += f"✅ <b>{achievement['name']}</b>\n"
            text += f"📝 {achievement['desc']}\n"
            text += f"📅 Получено: {date}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ежедневные награды с улучшенным интерфейсом"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    
    # Проверяем возможность получения награды
    can_claim = can_claim_daily_reward(p)
    current_streak = get_daily_streak(p)
    time_until = get_time_until_next_daily(p)
    
    if can_claim:
        result = claim_daily_reward(p)
        
        if result["success"]:
            streak = result["streak"]
            reward = result["reward"]
            
            text = (
                f"🎁 <b>Ежедневная награда получена!</b>\n\n"
                f"📅 День: {streak}/7\n"
                f"💰 Золото: +{reward['gold']}\n"
                f"⭐ XP: +{reward['xp']}\n"
                f"🎒 Предмет: {reward['item']}\n\n"
            )
            
            if streak == 7:
                text += "🎉 <b>Недельная серия завершена!</b>\n"
                text += "Завтра начнется новый цикл."
            else:
                text += f"🔥 Серия: {streak} дней подряд\n"
                text += "Заходите завтра за следующей наградой!"
        else:
            text = result["message"]
    else:
        # Показываем прогресс и время до следующей награды
        next_streak = current_streak + 1 if current_streak < 7 else 1
        next_reward = DAILY_REWARDS.get(next_streak, DAILY_REWARDS[1])
        
        text = (
            f"🎁 <b>Ежедневные награды</b>\n\n"
            f"📅 Текущая серия: {current_streak}/7\n"
            f"⏰ До следующей награды: {time_until}\n\n"
        )
        
        # Показываем следующую награду
        text += f"🎯 <b>Следующая награда (день {next_streak}):</b>\n"
        text += f"💰 Золото: +{next_reward['gold']}\n"
        text += f"⭐ XP: +{next_reward['xp']}\n"
        text += f"🎒 Предмет: {next_reward['item']}\n\n"
        
        # Показываем прогресс недели
        text += "📊 <b>Прогресс недели:</b>\n"
        for day in range(1, 8):
            if day <= current_streak:
                text += f"✅ День {day}: {DAILY_REWARDS[day]['gold']}💰 +{DAILY_REWARDS[day]['xp']}XP\n"
            else:
                text += f"⏳ День {day}: {DAILY_REWARDS[day]['gold']}💰 +{DAILY_REWARDS[day]['xp']}XP\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def pets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление питомцами"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    pets = p.get("pets", [])
    
    # Поля уже инициализированы в migrate_player_data()
    
    if not pets:
        await update.message.reply_text(
            "🐾 <b>Питомцы:</b>\n\n"
            "У вас пока нет питомцев.\n"
            "Питомцы дают бонусы к характеристикам!\n\n"
            "🎁 Получите питомца в приключениях или купите в магазине.",
            parse_mode="HTML",
            reply_markup=MAIN_KB
        )
        return
    
    text = "🐾 <b>Ваши питомцы:</b>\n\n"
    for pet_id in pets:
        if pet_id in PETS:
            pet = PETS[pet_id]
            text += f"{pet['emoji']} <b>{pet['name']}</b>\n"
            for stat, bonus in pet["bonus"].items():
                if stat == "attack":
                    text += f"🗡️ Атака +{bonus}\n"
                elif stat == "defense":
                    text += f"🛡️ Защита +{bonus}\n"
                elif stat == "hp":
                    text += f"❤️ HP +{bonus}\n"
                elif stat == "luck":
                    text += f"🍀 Удача +{bonus}\n"
                elif stat == "gold":
                    text += f"💰 Золото +{bonus}\n"
                elif stat == "xp":
                    text += f"⭐ XP +{bonus}\n"
            text += f"📊 Редкость: {pet['rarity'].title()}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def clans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление кланами"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    
    # Поля уже инициализированы в migrate_player_data()
    
    if p.get("clan"):
        # Показать информацию о клане
        clan_name = p["clan"]
        if clan_name in clans:
            clan = clans[clan_name]
            text = (
                f"🏰 <b>Клан: {clan['name']}</b>\n\n"
                f"👑 Лидер: {players[clan['leader']]['name']}\n"
                f"👥 Участников: {len(clan['members'])}/20\n"
                f"📊 Уровень: {clan['level']}\n"
                f"⭐ XP: {clan['xp']}\n"
                f"📝 Описание: {clan['description']}\n\n"
            )
            
            if clan["leader"] == uid:
                text += "👑 Вы лидер клана"
            else:
                text += "👤 Вы участник клана"
        else:
            text = "❌ Ошибка: клан не найден"
            p.pop("clan", None)  # Удаляем несуществующий клан
            save_players()
    else:
        # Показать список кланов
        if not clans:
            text = (
                "🏰 <b>Кланы:</b>\n\n"
                "Пока нет созданных кланов.\n"
                "Создайте свой клан!"
            )
        else:
            text = "🏰 <b>Доступные кланы:</b>\n\n"
            for clan_name, clan in clans.items():
                text += f"{clan['color']} <b>{clan['name']}</b>\n"
                text += f"👥 Участников: {len(clan['members'])}/20\n"
                text += f"👑 Лидер: {players[clan['leader']]['name']}\n\n"
    
    # Создаем клавиатуру с кнопками
    keyboard = build_clans_keyboard(p)
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)

async def pvp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """PvP система"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    
    # Поля уже инициализированы в migrate_player_data()
    
    wins = p["pvp_wins"]
    losses = p["pvp_losses"]
    total = wins + losses
    winrate = (wins / max(1, total)) * 100
    
    text = (
        f"⚔️ <b>PvP Статистика</b>\n\n"
        f"🏆 Победы: {wins}\n"
        f"💀 Поражения: {losses}\n"
        f"📊 Винрейт: {winrate:.1f}%\n\n"
        "Используйте /pvp_challenge [ID игрока] чтобы вызвать на дуэль!"
    )
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

def build_pvp_request_kb(duel_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"pvp:accept:{duel_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"pvp:decline:{duel_id}")]
    ])

def build_pvp_cancel_kb(duel_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Отменить вызов", callback_data=f"pvp:challenge_cancel:{duel_id}")]
    ])

def build_pvp_actions_kb(duel_id: str, is_active_turn: bool) -> InlineKeyboardMarkup:
    buttons: List[List[InlineKeyboardButton]] = []
    if is_active_turn:
        buttons.append([
            InlineKeyboardButton("🗡️ Атака", callback_data=f"pvp:act:{duel_id}:attack"),
            InlineKeyboardButton("✨ Способность", callback_data=f"pvp:act:{duel_id}:ability")
        ])
        buttons.append([
            InlineKeyboardButton("🧪 Зелье", callback_data=f"pvp:act:{duel_id}:potion"),
            InlineKeyboardButton("🏳️ Сдаться", callback_data=f"pvp:act:{duel_id}:surrender")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("🏳️ Сдаться", callback_data=f"pvp:act:{duel_id}:surrender")
        ])
    return InlineKeyboardMarkup(buttons)

def format_pvp_battle_text(duel_state: Dict[str, Any]) -> str:
    p1_name = duel_state["p1_name"]
    p2_name = duel_state["p2_name"]
    p1_hp = duel_state["p1"]["hp"]
    p2_hp = duel_state["p2"]["hp"]
    p1_max = duel_state["p1"]["max_hp"]
    p2_max = duel_state["p2"]["max_hp"]
    turn_name = p1_name if duel_state["turn"] == "p1" else p2_name
    log_lines = duel_state.get("log", [])[-6:]
    log = "\n".join(log_lines)
    return (
        f"⚔️ Дуэль: {p1_name} vs {p2_name}\n\n"
        f"{p1_name}: {p1_hp}/{p1_max} HP\n"
        f"{p2_name}: {p2_hp}/{p2_max} HP\n\n"
        f"Ход: {turn_name}\n\n"
        f"{log}"
    )

def is_in_duel(user_id: str) -> bool:
    return user_id in user_to_duel

async def pvp_challenge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда вызова игрока на дуэль: /pvp_challenge <user_id>"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    if not context.args:
        await update.message.reply_text("Использование: /pvp_challenge <ID игрока>")
        return
    to_id_raw = context.args[0]
    try:
        to_id_int = int(to_id_raw)
    except ValueError:
        await update.message.reply_text("Некорректный ID игрока")
        return
    to_id = str(to_id_int)
    if to_id == uid:
        await update.message.reply_text("Нельзя вызвать себя")
        return
    if to_id not in players:
        await update.message.reply_text("Этот игрок ещё не начал игру")
        return
    if is_in_duel(uid) or is_in_duel(to_id):
        await update.message.reply_text("Кто-то из участников уже в дуэли")
        return

    duel_id = f"{uid}_{to_id}_{int(datetime.now().timestamp())}"
    p_from = players[uid]
    p_to = players[to_id]

    # Регистрируем запрос
    pvp_requests[duel_id] = {
        "from_id": uid,
        "to_id": to_id,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "messages": {}
    }

    # Отправляем сообщения
    try:
        to_msg = await context.bot.send_message(
            chat_id=to_id_int,
            text=(
                f"⚔️ Вас вызывает на дуэль {p_from['name']} (ID {uid}).\n\n"
                f"Принять вызов?"
            ),
            reply_markup=build_pvp_request_kb(duel_id)
        )
        pvp_requests[duel_id]["messages"]["to"] = {"chat_id": to_msg.chat_id, "message_id": to_msg.message_id}
    except Exception:
        await update.message.reply_text("Не удалось доставить вызов. Вероятно, игрок не писал боту.")
        pvp_requests.pop(duel_id, None)
        return

    from_msg = await update.message.reply_text(
        f"⚔️ Вызов отправлен игроку {p_to['name']} (ID {to_id}). Ожидаем ответа...",
        reply_markup=build_pvp_cancel_kb(duel_id)
    )
    pvp_requests[duel_id]["messages"]["from"] = {"chat_id": from_msg.chat_id, "message_id": from_msg.message_id}

async def start_duel(context: ContextTypes.DEFAULT_TYPE, duel_id: str):
    req = pvp_requests.get(duel_id)
    if not req:
        return
    uid1 = req["from_id"]
    uid2 = req["to_id"]
    p1 = players[uid1]
    p2 = players[uid2]

    # Инициализируем боевые статы
    s1 = get_player_stats_with_pets(p1)
    s2 = get_player_stats_with_pets(p2)
    duel_state = {
        "id": duel_id,
        "p1_id": uid1,
        "p2_id": uid2,
        "p1_name": p1["name"],
        "p2_name": p2["name"],
        "p1": {"hp": s1["max_hp"], "max_hp": s1["max_hp"], "attack": s1["attack"], "defense": s1["defense"], "ability_used": False},
        "p2": {"hp": s2["max_hp"], "max_hp": s2["max_hp"], "attack": s2["attack"], "defense": s2["defense"], "ability_used": False},
        "turn": random.choice(["p1", "p2"]),
        "log": ["Дуэль началась!"] ,
        "messages": req.get("messages", {})
    }
    active_duels[duel_id] = duel_state
    user_to_duel[uid1] = duel_id
    user_to_duel[uid2] = duel_id

    text = format_pvp_battle_text(duel_state)
    msgs = duel_state["messages"]
    is_p1_turn = duel_state["turn"] == "p1"
    # Обновляем оба сообщения в боевой экран
    await safe_edit_message_by_id(context.bot, msgs["from"]["chat_id"], msgs["from"]["message_id"], text, reply_markup=build_pvp_actions_kb(duel_id, is_p1_turn))
    await safe_edit_message_by_id(context.bot, msgs["to"]["chat_id"], msgs["to"]["message_id"], text, reply_markup=build_pvp_actions_kb(duel_id, not is_p1_turn))

def end_duel(duel_id: str):
    duel = active_duels.pop(duel_id, None)
    if not duel:
        return None
    user_to_duel.pop(duel["p1_id"], None)
    user_to_duel.pop(duel["p2_id"], None)
    pvp_requests.pop(duel_id, None)
    return duel

async def update_duel_messages(context: ContextTypes.DEFAULT_TYPE, duel_state: Dict[str, Any]):
    text = format_pvp_battle_text(duel_state)
    msgs = duel_state["messages"]
    is_p1_turn = duel_state["turn"] == "p1"
    await safe_edit_message_by_id(context.bot, msgs["from"]["chat_id"], msgs["from"]["message_id"], text, reply_markup=build_pvp_actions_kb(duel_state["id"], is_p1_turn))
    await safe_edit_message_by_id(context.bot, msgs["to"]["chat_id"], msgs["to"]["message_id"], text, reply_markup=build_pvp_actions_kb(duel_state["id"], not is_p1_turn))

async def conclude_duel(context: ContextTypes.DEFAULT_TYPE, duel_state: Dict[str, Any], winner: str, loser: str, reason: str = ""):
    p_win = players[winner]
    p_lose = players[loser]
    p_win["pvp_wins"] = p_win.get("pvp_wins", 0) + 1
    p_lose["pvp_losses"] = p_lose.get("pvp_losses", 0) + 1
    # Небольшая награда победителю
    p_win["gold"] += 50
    p_win["xp"] += 100
    p_lose["xp"] += 20
    # Достижение
    check_achievements(p_win, "pvp_win")
    save_players()

    text = (
        f"🏁 Дуэль завершена!\n\n"
        f"Победитель: {players[winner]['name']}\n"
        f"Проигравший: {players[loser]['name']}\n"
        + (f"Причина: {reason}\n\n" if reason else "\n")
        + f"Награда победителю: +50💰, +100XP\n"
        + f"Проигравшему: +20XP"
    )
    msgs = duel_state["messages"]
    # Завершаем: убираем кнопки
    await safe_edit_message_by_id(context.bot, msgs["from"]["chat_id"], msgs["from"]["message_id"], text)
    await safe_edit_message_by_id(context.bot, msgs["to"]["chat_id"], msgs["to"]["message_id"], text)
    end_duel(duel_state["id"]) 

async def pvp_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    parts = query.data.split(":")
    if len(parts) < 2:
        return
    action = parts[1]

    # Обработка отмены вызова до начала дуэли
    if action == "challenge_cancel":
        if len(parts) < 3:
            return
        duel_id = parts[2]
        req = pvp_requests.get(duel_id)
        if not req or req.get("status") != "pending":
            await safe_edit_message_text(query, "⚠️ Вызов уже неактуален")
            return
        if req["from_id"] != uid:
            await query.answer("Отменить может только вызывающий", show_alert=True)
            return
        # Удаляем запрос и обновляем оба сообщения
        msgs = req.get("messages", {})
        try:
            if "to" in msgs:
                await safe_edit_message_by_id(context.bot, msgs["to"]["chat_id"], msgs["to"]["message_id"], "Вызов отменён")
        except Exception:
            pass
        await safe_edit_message_text(query, "Вы отменили вызов")
        pvp_requests.pop(duel_id, None)
        return

    # Принятие/отклонение вызова
    if action in ("accept", "decline"):
        if len(parts) < 3:
            return
        duel_id = parts[2]
        req = pvp_requests.get(duel_id)
        if not req or req.get("status") != "pending":
            await safe_edit_message_text(query, "⚠️ Вызов уже неактуален")
            return
        if uid != req["to_id"]:
            await query.answer("Это приглашение не вам", show_alert=True)
            return
        if action == "decline":
            # Сообщаем обеим сторонам
            msgs = req.get("messages", {})
            await safe_edit_message_text(query, "Вы отклонили вызов")
            if "from" in msgs:
                await safe_edit_message_by_id(context.bot, msgs["from"]["chat_id"], msgs["from"]["message_id"], "Ваш вызов отклонён")
            pvp_requests.pop(duel_id, None)
            return
        # accept
        if is_in_duel(req["from_id"]) or is_in_duel(req["to_id"]):
            await safe_edit_message_text(query, "Кто-то из участников уже в другой дуэли")
            return
        req["status"] = "accepted"
        await start_duel(context, duel_id)
        return

    # Действия в дуэли
    if action == "act":
        if len(parts) < 4:
            return
        duel_id = parts[2]
        cmd = parts[3]
        duel = active_duels.get(duel_id)
        if not duel:
            await safe_edit_message_text(query, "⚠️ Дуэль завершена")
            return
        is_p1 = uid == duel["p1_id"]
        is_p2 = uid == duel["p2_id"]
        if not (is_p1 or is_p2):
            await query.answer("Вы не участник этой дуэли", show_alert=True)
            return
        turn_key = duel["turn"]
        if (turn_key == "p1" and not is_p1) or (turn_key == "p2" and not is_p2):
            # Разрешим сдаться в любой момент
            if cmd != "surrender":
                await query.answer("Сейчас не ваш ход", show_alert=True)
                return
        attacker_key = "p1" if is_p1 else "p2"
        defender_key = "p2" if is_p1 else "p1"
        attacker_id = duel["p1_id"] if is_p1 else duel["p2_id"]
        defender_id = duel["p2_id"] if is_p1 else duel["p1_id"]
        attacker_p = players[attacker_id]
        defender_p = players[defender_id]

        # Собираем статы (атака/защита фиксированы при старте в duel state)
        atk_stat = duel[attacker_key]["attack"]
        def_stat = duel[defender_key]["defense"]

        log_add = ""
        if cmd == "attack":
            dmg = dmg_roll(atk_stat, def_stat)
            duel[defender_key]["hp"] = max(0, duel[defender_key]["hp"] - dmg)
            log_add = f"{attacker_p['name']} атакует и наносит {dmg} урона."
        elif cmd == "ability":
            if duel[attacker_key]["ability_used"]:
                await query.answer("Способность уже использована", show_alert=True)
                return
            cls = attacker_p.get("class")
            if cls == "⚔️ Воин":
                dmg = dmg_roll(atk_stat, def_stat) * 2
            elif cls == "🧙 Маг":
                dmg = 15
            elif cls == "🕵️ Вор":
                dmg = max(1, duel[attacker_key]["attack"] + random.randint(0, 2))
            else:
                dmg = dmg_roll(atk_stat, def_stat)
            duel[defender_key]["hp"] = max(0, duel[defender_key]["hp"] - dmg)
            duel[attacker_key]["ability_used"] = True
            log_add = f"{attacker_p['name']} применяет способность и наносит {dmg} урона!"
        elif cmd == "potion":
            # Пьём малое зелье
            if consume_item(attacker_p, "Малое зелье лечения", 1):
                healed = min(35, duel[attacker_key]["max_hp"] - duel[attacker_key]["hp"])
                duel[attacker_key]["hp"] += healed
                log_add = f"{attacker_p['name']} выпивает зелье (+{healed} HP)."
            else:
                await query.answer("Нет Малых зелий лечения", show_alert=True)
                return
        elif cmd == "surrender":
            duel[attacker_key]["hp"] = 0
            log_add = f"{attacker_p['name']} сдаётся!"
        else:
            return

        duel.setdefault("log", []).append(log_add)

        # Проверяем конец дуэли
        if duel[defender_key]["hp"] <= 0 or duel[attacker_key]["hp"] <= 0:
            winner = attacker_id if duel[defender_key]["hp"] <= 0 else defender_id
            loser = defender_id if winner == attacker_id else attacker_id
            await conclude_duel(context, duel, winner, loser, reason=("сдача" if cmd == "surrender" else ""))
            return

        # Переход хода, если действие было не лечением? В любом случае меняем ход.
        duel["turn"] = defender_key
        await update_duel_messages(context, duel)
        return

async def inventory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    if not p["inventory"]:
        await update.message.reply_text("🎒 <b>Твой инвентарь пуст.</b>", parse_mode="HTML", reply_markup=MAIN_KB)
        return
    
    items = "\n".join(f"▪️ {item} ×{count}" for item, count in p["inventory"].items())
    await update.message.reply_text(
        f"🎒 <b>Инвентарь:</b>\n\n{items}\n\n"
        "ℹ️ Используй /use_potion для лечения",
        parse_mode="HTML",
        reply_markup=MAIN_KB
    )

async def use_potion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    item = "Малое зелье лечения"
    if p["hp"] >= p["max_hp"]:
        await update.message.reply_text("❤️ У тебя полное здоровье!")
        return
    if consume_item(p, item, 1):
        healed = heal_player(p, 35)
        await update.message.reply_text(f"🧪 Ты выпил зелье и восстановил {healed} HP. Теперь: {p['hp']}/{p['max_hp']}")
    else:
        await update.message.reply_text("❌ Нет Малых зелий лечения в инвентаре.")

async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    query = getattr(update, "callback_query", None)

    if uid not in players:
        if query:
            await safe_edit_message_text(query, "Сначала нажми /start")
        else:
            await update.message.reply_text("Сначала нажми /start")
        return

    p = players[uid]
    q = p["quests"]

    if not q:
        # Генерируем первый квест
        new_quest = generate_random_quest(p["level"])
        quest_id = f"random_quest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        p["quests"][quest_id] = {
            **new_quest,
            "progress": 0,
            "status": "active"
        }
        save_players()
        q = p["quests"]

    quests_text: List[str] = []
    active_count = 0
    completed_count = 0

    for quest_id, quest in q.items():
        status = "✅" if quest.get("status") == "completed" else "⌛"
        if quest.get("status") == "active":
            active_count += 1
        else:
            completed_count += 1

        quests_text.append(
            f"{status} <b>{quest.get('title', 'Без названия')}</b>\n"
            f"📝 {quest.get('desc', '')}\n"
            f"📊 Прогресс: {quest.get('progress', 0)}/{quest.get('required', 0)}\n"
        )

    # Показываем статистику квестов
    stats_text = (
        f"📊 <b>Статистика квестов:</b>\n"
        f"⌛ Активных: {active_count}\n"
        f"✅ Завершенных: {completed_count}\n\n"
    )

    # Кнопки для управления квестами
    keyboard: List[List[InlineKeyboardButton]] = []
    if active_count < 3:  # Максимум 3 активных квеста
        keyboard.append([InlineKeyboardButton("🎯 Новый квест", callback_data="quest:new")])
    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="quest:refresh")])
    keyboard.append([InlineKeyboardButton("🚪 Закрыть", callback_data="quest:close")])

    text = f"📜 <b>Активные квесты:</b>\n\n{stats_text}" + "\n".join(quests_text)

    if query:
        await safe_edit_message_text(query, text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def adventure_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    # Проверка активного боя, торговца или дуэли
    if context.user_data.get("battle") or context.user_data.get("merchant_active") or (uid in user_to_duel):
        await update.message.reply_text(
            "⚠️ Сначала завершите текущее событие (бой/торговля/дуэль)!",
            reply_markup=MAIN_KB
        )
        return
    
    # Проверка кулдауна
    last_adventure = context.user_data.get("last_adventure")
    if last_adventure:
        cooldown = 6
        elapsed = (datetime.now() - last_adventure).total_seconds()
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            await update.message.reply_text(
                f"Ты устал. Отдохни ещё {remaining} секунд.",
                reply_markup=MAIN_KB
            )
            return
    
    p = players[uid]
    context.user_data["last_adventure"] = datetime.now()
    
    event = random.choice(["fight", "gold", "item", "merchant", "pet", "treasure", "mystery"])
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
        await update.message.reply_text(f"💰 Ты нашёл мешочек золота: +{gain} 💰. Теперь у тебя {p['gold']} золота.")
    elif event == "item":
        item = random.choice(list(SHOP_ITEMS.keys()))
        add_item(p, item, 1)
        await update.message.reply_text(f"🎒 Ты нашёл предмет: {item}! Он добавлен в инвентарь.")
    elif event == "merchant":
        context.user_data["merchant_active"] = True
        await update.message.reply_text(
            "🛒 Тебе повстречался странствующий торговец:",
            reply_markup=build_shop_kb()
        )
    elif event == "pet":
        # Шанс получить питомца
        if random.random() < 0.1:  # 10% шанс
            available_pets = [pet_id for pet_id in PETS.keys() if pet_id not in p.get("pets", [])]
            if available_pets:
                pet_id = random.choice(available_pets)
                p["pets"].append(pet_id)
                pet = PETS[pet_id]
                check_achievements(p, "pet_obtained")
                save_players()
                await update.message.reply_text(
                    f"🐾 Поздравляем! Вы нашли питомца: {pet['emoji']} {pet['name']}!\n"
                    f"📊 Редкость: {pet['rarity'].title()}\n"
                    "Питомец даёт бонусы к характеристикам!"
                )
            else:
                await update.message.reply_text("🐾 Вы уже собрали всех питомцев! Отличная коллекция!")
        else:
            await update.message.reply_text("🐾 Вы встретили дикое животное, но оно убежало...")
    elif event == "treasure":
        # Сокровище с большими наградами
        gold_gain = random.randint(30, 60)
        xp_gain = random.randint(20, 40)
        p["gold"] += gold_gain
        p["xp"] += xp_gain
        save_players()
        await update.message.reply_text(
            f"💎 Сокровище! Вы нашли:\n"
            f"💰 Золото: +{gold_gain}\n"
            f"⭐ XP: +{xp_gain}\n"
            f"Теперь у вас {p['gold']} золота и {p['xp']} XP!"
        )
    elif event == "mystery":
        # Таинственное событие
        mystery_events = [
            ("🧙 Мудрец благословил вас", {"hp": 20, "xp": 15}),
            ("🍀 Удача улыбнулась", {"gold": 25, "luck": 1}),
            ("⚡ Энергия наполнила вас", {"attack": 1, "defense": 1}),
            ("🔮 Магический кристалл", {"xp": 30, "item": "Эликсир удачи"}),
        ]
        event_name, bonuses = random.choice(mystery_events)
        
        for stat, bonus in bonuses.items():
            if stat == "hp":
                p["hp"] = min(p["max_hp"], p["hp"] + bonus)
            elif stat == "xp":
                p["xp"] += bonus
            elif stat == "gold":
                p["gold"] += bonus
            elif stat == "luck":
                p["luck"] = p.get("luck", 0) + bonus
            elif stat == "attack":
                p["attack"] += bonus
            elif stat == "defense":
                p["defense"] += bonus
            elif stat == "item":
                add_item(p, bonus, 1)
        
        save_players()
        await update.message.reply_text(
            f"🔮 {event_name}!\n"
            f"Вы получили бонусы к характеристикам!"
        )

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    await update.message.reply_text("Лавка торговца:", reply_markup=build_shop_kb(p))

async def businesses_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    await update.message.reply_text(
        "💼 Бизнесы: покупай и получай пассивный доход!\n\n"
        "— Доход начисляется каждую минуту.\n"
        "— Улучшения увеличивают доход x уровню.",
        reply_markup=build_businesses_kb(p)
    )

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "Сначала нажми /start")
        return
    
    p = players[uid]
    data = query.data # shop:buy:ITEM, shop:bulk:ITEM, shop:close, shop:already_owned, shop:balance, shop:back

    if data == "shop:close":
        context.user_data.pop("merchant_active", None)
        await safe_edit_message_text(query, "Торговец уходит в туман...")
        return
    
    if data == "shop:already_owned":
        await query.answer("У тебя уже есть этот питомец!")
        return
    
    if data == "shop:balance":
        await query.answer(f"💰 Ваш баланс: {p['gold']} золота", show_alert=True)
        return
    
    if data == "shop:back":
        await safe_edit_message_text(
            query,
            "Лавка торговца:",
            reply_markup=build_shop_kb(p)
        )
        return
    
    if data == "shop:bulk":
        await safe_edit_message_text(
            query,
            "🛒 <b>Массовая покупка</b>\n\n"
            "Выберите предмет для массовой покупки:",
            parse_mode="HTML",
            reply_markup=build_bulk_shop_kb(p)
        )
        return
    
    if data.startswith("shop:bulk:"):
        _, _, item_name = data.split(":", 2)
        if item_name not in SHOP_ITEMS:
            await safe_edit_message_text(query, "Такого товара нет.")
            return
        
        # Начинаем процесс массовой покупки
        context.user_data["bulk_buy_item"] = item_name
        context.user_data["awaiting_bulk_amount"] = True
        
        price = SHOP_ITEMS[item_name]["price"]
        max_affordable = p["gold"] // price
        
        await safe_edit_message_text(
            query,
            f"🛒 <b>Массовая покупка: {item_name}</b>\n\n"
            f"💰 Цена за штуку: {price} золота\n"
            f"💰 Ваш баланс: {p['gold']} золота\n"
            f"📦 Максимум можете купить: {max_affordable} штук\n\n"
            "✍️ Введите количество для покупки:",
            parse_mode="HTML"
        )
        return
    
    if data.startswith("shop:category:"):
        _, _, category = data.split(":", 2)
        category_items = []
        
        for item_name, meta in SHOP_ITEMS.items():
            if meta["type"] == category:
                category_items.append((item_name, meta))
        
        if not category_items:
            await query.answer("В этой категории нет товаров", show_alert=True)
            return
        
        buttons = []
        for item_name, meta in category_items:
            emoji = meta.get("emoji", "📦")
            price = meta['price']
            inventory_count = p["inventory"].get(item_name, 0)
            
            if category == "pet":
                pet_id = meta["pet_id"]
                if pet_id in p.get("pets", []):
                    buttons.append([InlineKeyboardButton(f"{emoji} {item_name} ✅ (Уже есть)", callback_data="shop:already_owned")])
                else:
                    buttons.append([InlineKeyboardButton(f"{emoji} {item_name} ({price}💰)", callback_data=f"shop:buy:{item_name}")])
            else:
                buttons.append([InlineKeyboardButton(f"{emoji} {item_name} ({price}💰) x{inventory_count}", callback_data=f"shop:buy:{item_name}")])
        
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="shop:back")])
        
        category_names = {"consumable": "🧪 Потребляемые", "equipment": "⚔️ Экипировка", "pet": "🐾 Питомцы"}
        category_name = category_names.get(category, category.title())
        
        await safe_edit_message_text(
            query,
            f"🛒 <b>{category_name}</b>\n\n"
            "Выберите товар для покупки:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    _, action, item_name = data.split(":", 2)
    if action == "buy":
        if item_name not in SHOP_ITEMS:
            await safe_edit_message_text(query, "Такого товара нет.")
            return
        
        price = SHOP_ITEMS[item_name]["price"]
        if p["gold"] < price:
            await safe_edit_message_text(
                query,
                f"❌ Недостаточно золота для покупки {item_name}.\n"
                f"Нужно {price}💰, у вас {p['gold']}💰.",
                reply_markup=build_shop_kb(p)
            )
            return

        p["gold"] -= price
        emoji = SHOP_ITEMS[item_name].get("emoji", "📦")
        
        if SHOP_ITEMS[item_name]["type"] == "consumable":
            add_item(p, item_name, 1)
            await safe_edit_message_text(
                query,
                f"{emoji} Ты купил: {item_name}. В инвентаре пополнение!\n"
                f"💰 Текущий баланс: {p['gold']}💰",
                reply_markup=build_shop_kb(p)
            )
        elif SHOP_ITEMS[item_name]["type"] == "equipment":
            # Применяем эффекты экипировки
            effect = SHOP_ITEMS[item_name]["effect"]
            if "attack_plus" in effect:
                p["attack"] += effect["attack_plus"]
            if "defense_plus" in effect:
                p["defense"] += effect["defense_plus"]
            if "luck_plus" in effect:
                p["luck"] = p.get("luck", 0) + effect["luck_plus"]
            save_players()
            await safe_edit_message_text(
                query,
                f"{emoji} Ты купил и экипировал: {item_name}. Твоя сила растёт!\n"
                f"💰 Текущий баланс: {p['gold']}💰",
                reply_markup=build_shop_kb(p)
            )
        elif SHOP_ITEMS[item_name]["type"] == "pet":
            # Покупаем питомца
            pet_id = SHOP_ITEMS[item_name]["pet_id"]
            if pet_id not in p.get("pets", []):
                p.setdefault("pets", []).append(pet_id)
                save_players()
                # Проверяем достижения
                check_achievements(p, "pet_check", len(p["pets"]))
                await safe_edit_message_text(
                    query,
                    f"{emoji} Ты купил питомца: {item_name}! Теперь у тебя {len(p['pets'])} питомцев.\n"
                    f"💰 Текущий баланс: {p['gold']}💰",
                    reply_markup=build_shop_kb(p)
                )
            else:
                # Возвращаем золото, если питомец уже есть
                p["gold"] += price
                await safe_edit_message_text(
                    query,
                    f"❌ У тебя уже есть питомец {item_name}! Золото возвращено.\n"
                    f"💰 Текущий баланс: {p['gold']}💰",
                    reply_markup=build_shop_kb(p)
                )

async def businesses_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "Сначала нажми /start")
        return
    p = players[uid]
    data = query.data  # biz:buy:ID | biz:upgrade:ID | biz:claim | biz:upgrade_all | biz:close | biz:details | biz:info

    if data == "biz:close":
        await safe_edit_message_text(query, "Закрыто.")
        return
    
    if data == "biz:info":
        income_info = get_business_income_info(p)
        text = (
            f"💼 <b>Информация о бизнесах</b>\n\n"
            f"💰 Общий доход: {income_info['total_per_min']}/мин\n"
            f"📈 Доход в час: {income_info['total_per_hour']}\n"
            f"📦 Владений: {len(p.get('businesses', {}))}\n\n"
        )
        
        if income_info["businesses"]:
            text += "<b>Ваши бизнесы:</b>\n"
            for biz in income_info["businesses"]:
                text += f"• {biz['name']} ур.{biz['level']} ({biz['income_per_min']}/мин)\n"
        
        await safe_edit_message_text(query, text, parse_mode="HTML", reply_markup=build_businesses_kb(p))
        return
    
    if data == "biz:details":
        income_info = get_business_income_info(p)
        text = "💼 <b>Детальная информация о бизнесах</b>\n\n"
        
        if income_info["businesses"]:
            for biz in income_info["businesses"]:
                text += (
                    f"🏢 <b>{biz['name']}</b>\n"
                    f"📊 Уровень: {biz['level']}\n"
                    f"💰 Доход: {biz['income_per_min']}/мин ({biz['income_per_hour']}/час)\n"
                    f"⚡ Стоимость улучшения: {biz['upgrade_cost']}💰\n\n"
                )
        else:
            text += "У вас пока нет бизнесов.\n"
        
        await safe_edit_message_text(query, text, parse_mode="HTML", reply_markup=build_businesses_kb(p))
        return
    
    if data == "biz:claim":
        last = p.get("last_business_claim")
        now = datetime.now()
        if last:
            last_dt = datetime.fromisoformat(last)
        else:
            last_dt = now
            p["last_business_claim"] = now.isoformat()
        
        minutes = max(0, int((now - last_dt).total_seconds() // 60))
        owned = p.get("businesses", {})
        total_income = 0
        
        for biz_id, meta in owned.items():
            base = BUSINESSES.get(biz_id, {}).get("income_per_min", 0)
            level = meta.get("level", 1)
            total_income += base * level * minutes
        
        p["gold"] += total_income
        p["last_business_claim"] = now.isoformat()
        save_players()
        
        await safe_edit_message_text(
            query,
            f"📥 Получено: {total_income}💰 за {minutes} мин.\n"
            f"💰 Текущий баланс: {p['gold']}💰",
            reply_markup=build_businesses_kb(p)
        )
        return
    
    if data == "biz:upgrade_all":
        owned = p.setdefault("businesses", {})
        if not owned:
            await query.answer("У вас нет бизнесов для улучшения!", show_alert=True)
            return
        
        cost = 0
        for biz_id in owned.keys():
            cost += int(BUSINESSES[biz_id]["price"] * 0.5)
        
        if p["gold"] < cost:
            await safe_edit_message_text(
                query,
                f"❌ Недостаточно золота для улучшения всех бизнесов.\n"
                f"Нужно {cost}💰, у вас {p['gold']}💰.",
                reply_markup=build_businesses_kb(p)
            )
            return
        
        p["gold"] -= cost
        for biz_id in owned.keys():
            owned[biz_id]["level"] = owned[biz_id].get("level", 1) + 1
        
        save_players()
        await safe_edit_message_text(
            query,
            f"✅ Все бизнесы улучшены!\n"
            f"💸 Потрачено: {cost}💰\n"
            f"💰 Текущий баланс: {p['gold']}💰",
            reply_markup=build_businesses_kb(p)
        )
        return
    
    if data.startswith("biz:upgrade:"):
        _, _, biz_id = data.split(":", 2)
        if biz_id not in BUSINESSES:
            await query.answer("Такого бизнеса нет", show_alert=True)
            return
        
        if biz_id not in p.get("businesses", {}):
            await query.answer("У вас нет этого бизнеса", show_alert=True)
            return
        
        upgrade_cost = int(BUSINESSES[biz_id]["price"] * 0.5)
        if p["gold"] < upgrade_cost:
            await safe_edit_message_text(
                query,
                f"❌ Недостаточно золота для улучшения {BUSINESSES[biz_id]['name']}.\n"
                f"Нужно {upgrade_cost}💰, у вас {p['gold']}💰.",
                reply_markup=build_businesses_kb(p)
            )
            return
        
        p["gold"] -= upgrade_cost
        p["businesses"][biz_id]["level"] = p["businesses"][biz_id].get("level", 1) + 1
        save_players()
        
        await safe_edit_message_text(
            query,
            f"✅ {BUSINESSES[biz_id]['name']} улучшен!\n"
            f"💸 Потрачено: {upgrade_cost}💰\n"
            f"💰 Текущий баланс: {p['gold']}💰",
            reply_markup=build_businesses_kb(p)
        )
        return
    
    if data.startswith("biz:buy:"):
        _, _, biz_id = data.split(":", 2)
        if biz_id not in BUSINESSES:
            await query.answer("Такого бизнеса нет", show_alert=True)
            return
        
        if biz_id in p.get("businesses", {}):
            await query.answer("Уже куплено", show_alert=True)
            return
        
        price = BUSINESSES[biz_id]["price"]
        if p["gold"] < price:
            await safe_edit_message_text(
                query,
                f"❌ Недостаточно золота для покупки {BUSINESSES[biz_id]['name']}.\n"
                f"Нужно {price}💰, у вас {p['gold']}💰.",
                reply_markup=build_businesses_kb(p)
            )
            return
        
        p["gold"] -= price
        p.setdefault("businesses", {})[biz_id] = {"level": 1, "bought_at": datetime.now().isoformat()}
        if not p.get("last_business_claim"):
            p["last_business_claim"] = datetime.now().isoformat()
        
        # Проверяем достижения
        check_achievements(p, "business_check")
        
        save_players()
        await safe_edit_message_text(
            query,
            f"💼 Куплен бизнес: {BUSINESSES[biz_id]['name']} за {price}💰.\n"
            f"💰 Текущий баланс: {p['gold']}💰",
            reply_markup=build_businesses_kb(p)
        )
        return

async def casino_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /casino"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала начните игру командой /start")
        return
    
    p = players[uid]
    # Сбрасываем прошлую ставку и переводим пользователя в режим ожидания ввода ставки
    context.user_data.pop("casino_bet", None)
    context.user_data["awaiting_casino_bet"] = True
    await update.message.reply_text(
        f"🎰 <b>Добро пожаловать в казино!</b>\n"
        f"💰 Ваш баланс: {p['gold']} золота\n\n"
        "✍️ Введите сумму ставки (число) или процент от баланса (например, 25%):",
        parse_mode="HTML"
    )

async def casino_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода ставки для казино"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала начните игру командой /start")
        return
    
    p = players[uid]
    # Обрабатываем ввод только если мы действительно ожидаем ставку
    if not context.user_data.get("awaiting_casino_bet"):
        return
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
        await update.message.reply_text("❌ Введите число или процент (например: 50 или 25%)")
        return
    
    min_bet = min(game["min_bet"] for game in CASINO_GAMES.values())
    if bet < min_bet:
        await update.message.reply_text(f"❌ Минимальная ставка: {min_bet} золота")
        return
    if bet > p["gold"]:
        await update.message.reply_text(f"❌ Недостаточно золота. Ваш баланс: {p['gold']}")
        return
    
    context.user_data["casino_bet"] = bet
    context.user_data["awaiting_casino_bet"] = False
    await show_casino_games(update, context)

async def show_casino_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ игр после ввода ставки"""
    bet = context.user_data["casino_bet"]
    
    await update.message.reply_text(
        f"💰 Ваша ставка: <b>{bet}</b> золота\n"
        "🎮 Выберите игру:\n\n"
        "🎯 Удвоение - шанс выигрыша 45%, множитель x2\n"
        "🎲 Кости - шанс выигрыша 50%, множитель x1.5\n"
        "🎡 Рулетка - шанс выигрыша 40%, множитель x2\n"
        "🎰 Слоты - шанс выигрыша 30%, множитель x3\n"
        "🃏 Блэкджек - шанс выигрыша 48%, множитель x2.5",
        parse_mode="HTML",
        reply_markup=build_casino_games_kb()
    )

async def casino_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок казино с улучшенной функциональностью"""
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "❌ Сначала начните игру (/start)")
        return
    
    p = players[uid]
    data = query.data.split(":")
    
    if data[1] == "exit":
        context.user_data.pop("casino_bet", None)
        context.user_data.pop("awaiting_casino_bet", None)
        await safe_edit_message_text(query, "🚪 Вы покинули казино. Удачи в приключениях!")
        return
    
    elif data[1] == "back":
        await safe_edit_message_text(
            query,
            f"🎰 <b>Добро пожаловать в казино!</b>\n"
            f"💰 Ваш баланс: {p['gold']} золота\n\n"
            "✍️ Введите сумму ставки (число) или процент от баланса (например, 25%):",
            parse_mode="HTML"
        )
        return
    
    elif data[1] == "quick_bets":
        await safe_edit_message_text(
            query,
            f"⚡ <b>Быстрые ставки</b>\n"
            f"💰 Ваш баланс: {p['gold']} золота\n\n"
            "Выберите сумму ставки:",
            parse_mode="HTML",
            reply_markup=build_quick_bets_kb(p)
        )
        return
    
    elif data[1] == "quick_bet":
        if len(data) < 3:
            await query.answer("Ошибка: не указана сумма ставки", show_alert=True)
            return
        
        try:
            bet = int(data[2])
        except ValueError:
            await query.answer("Ошибка: неверная сумма ставки", show_alert=True)
            return
        
        if bet > p["gold"]:
            await query.answer("❌ Недостаточно золота!", show_alert=True)
            return
        
        context.user_data["casino_bet"] = bet
        await safe_edit_message_text(
            query,
            f"💰 Ваша ставка: <b>{bet}</b> золота\n"
            "🎮 Выберите игру:\n\n"
            "🎯 Удвоение - шанс выигрыша 45%, множитель x2\n"
            "🎲 Кости - шанс выигрыша 50%, множитель x1.5\n"
            "🎡 Рулетка - шанс выигрыша 40%, множитель x2\n"
            "🎰 Слоты - шанс выигрыша 30%, множитель x3\n"
            "🃏 Блэкджек - шанс выигрыша 48%, множитель x2.5",
            parse_mode="HTML",
            reply_markup=build_casino_games_kb()
        )
        return
    
    elif data[1] == "history":
        stats = get_casino_stats(p)
        history = p.get("casino_history", [])
        
        text = (
            f"📊 <b>Статистика казино</b>\n\n"
            f"🎮 Всего игр: {stats['total_games']}\n"
            f"🏆 Победы: {stats['wins']}\n"
            f"💀 Поражения: {stats['losses']}\n"
            f"📈 Винрейт: {stats['winrate']:.1f}%\n"
            f"💰 Общий профит: {stats['total_profit']} золота\n\n"
        )
        
        if history:
            text += "<b>Последние 5 игр:</b>\n"
            for entry in history[-5:]:
                game_name = CASINO_GAMES[entry["game"]]["name"]
                result = "✅" if entry["result"] else "❌"
                profit = entry["prize"] - entry["bet"]
                text += f"{result} {game_name}: {entry['bet']}💰 → {profit:+d}💰\n"
        else:
            text += "История игр пуста."
        
        await safe_edit_message_text(
            query,
            text,
            parse_mode="HTML",
            reply_markup=build_casino_games_kb()
        )
        return
    
    elif data[1] == "change_bet":
        context.user_data.pop("casino_bet", None)
        context.user_data["awaiting_casino_bet"] = True
        await safe_edit_message_text(
            query,
            f"✍️ Введите новую сумму ставки (число) или процент от баланса (например, 25%):\n"
            f"💰 Ваш текущий баланс: {p['gold']} золота",
            parse_mode="HTML"
        )
        return
    
    elif data[1] == "balance":
        await query.answer(f"Ваш баланс: {p['gold']} золота", show_alert=True)
        return
    
    elif data[1] == "no_money":
        await query.answer("❌ Недостаточно золота для этой игры!", show_alert=True)
        return
    
    # Определяем ставку
    bet = context.user_data.get("casino_bet")
    game_type = data[1]
    
    if bet is None:
        await query.answer("Сначала введите ставку сообщением в чате.", show_alert=True)
        return
    
    result = play_casino_game(p, game_type, bet)
    
    # Добавляем в историю
    if result["success"] is not None:  # Не добавляем кулдауны
        add_casino_history(p, game_type, bet, result["success"], result.get("prize", 0))
    
    save_players()
    
    # Формируем полное сообщение
    message = (
        f"🎰 <b>{CASINO_GAMES[game_type]['name']}</b>\n"
        f"💵 Ставка: <b>{bet}</b> золота\n\n"
        f"{result['message']}\n\n"
        f"💰 Текущий баланс: <b>{p['gold']}</b> золота\n\n"
    )
    
    if "Подождите" in result["message"]:
        await query.answer(result["message"], show_alert=True)
        await safe_edit_message_text(
            query,
            message,
            parse_mode="HTML",
            reply_markup=build_casino_games_kb()
        )
        return
    
    if result["success"] is False:
        message += "😔 Не повезло... Попробуйте ещё раз!"
    elif result["success"] is True:
        message += "🎉 Отличный результат! Хотите сыграть ещё?"
    else:
        message += "🤝 Ничья! Попробуйте ещё раз."
    
    await safe_edit_message_text(
        query,
        message,
        parse_mode="HTML",
        reply_markup=build_casino_games_kb()
    )

async def clan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок кланов"""
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "❌ Сначала начните игру (/start)")
        return
    
    p = players[uid]
    data = query.data.split(":")
    action = data[1]
    
    if action == "create":
        # Начинаем процесс создания клана
        context.user_data["clan_creation"] = True
        await safe_edit_message_text(
            query,
            "🏗️ <b>Создание клана</b>\n\n"
            "✍️ Введите название клана (от 3 до 20 символов):\n\n"
            "ℹ️ Название должно быть уникальным и содержать только буквы, цифры и пробелы.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([])
        )
        return
    
    elif action == "join":
        if len(data) < 3:
            await query.answer("❌ Ошибка: не указан клан", show_alert=True)
            return
        
        clan_name = data[2]
        if clan_name not in clans:
            await query.answer("❌ Клан не найден", show_alert=True)
            return
        
        if p.get("clan"):
            await query.answer("❌ Вы уже состоите в клане", show_alert=True)
            return
        
        if join_clan(clan_name, uid):
            save_players()
            save_clans()
            await query.answer(f"✅ Вы присоединились к клану {clan_name}!", show_alert=True)
        else:
            await query.answer("❌ Не удалось присоединиться к клану", show_alert=True)
        
        # Обновляем сообщение
        await refresh_clan_message(query, p)
        return
    
    elif action == "leave":
        if not p.get("clan"):
            await query.answer("❌ Вы не состоите в клане", show_alert=True)
            return
        
        clan_name = p["clan"]
        if leave_clan(uid):
            save_players()
            save_clans()
            await query.answer(f"✅ Вы покинули клан {clan_name}", show_alert=True)
        else:
            await query.answer("❌ Не удалось покинуть клан", show_alert=True)
        
        # Обновляем сообщение
        await refresh_clan_message(query, p)
        return
    
    elif action == "refresh":
        # Обновляем сообщение
        await refresh_clan_message(query, p)
        return
    
    elif action == "main_menu":
        # Возвращаемся в главное меню
        await query.message.reply_text(
            "🏠 <b>Главное меню</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=MAIN_KB
        )
        await query.delete_message()
        return

async def handle_clan_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка создания клана"""
    msg = update.message
    uid = str(update.effective_user.id)
    
    if uid not in players:
        await msg.reply_text("❌ Сначала начните игру (/start)")
        return
    
    p = players[uid]
    clan_name = msg.text.strip()
    
    # Проверяем, что игрок не в клане
    if p.get("clan"):
        context.user_data.pop("clan_creation", None)
        await msg.reply_text("❌ Вы уже состоите в клане!", reply_markup=MAIN_KB)
        return
    
    # Валидация названия клана
    if len(clan_name) < 3 or len(clan_name) > 20:
        await msg.reply_text(
            "❌ Название клана должно быть от 3 до 20 символов.\n"
            "Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    # Проверяем, что название содержит только допустимые символы
    if not clan_name.replace(" ", "").replace("-", "").replace("_", "").isalnum():
        await msg.reply_text(
            "❌ Название клана может содержать только буквы, цифры, пробелы, дефисы и подчеркивания.\n"
            "Попробуйте ещё раз:",
            parse_mode="HTML"
        )
        return
    
    # Проверяем уникальность названия
    if clan_name in clans:
        await msg.reply_text(
            f"❌ Клан с названием '{clan_name}' уже существует.\n"
            "Попробуйте другое название:",
            parse_mode="HTML"
        )
        return
    
    # Создаем клан
    if create_clan(clan_name, uid, p["name"]):
        save_players()
        save_clans()
        context.user_data.pop("clan_creation", None)
        
        await msg.reply_text(
            f"🎉 <b>Клан создан!</b>\n\n"
            f"🏰 Название: {clan_name}\n"
            f"👑 Лидер: {p['name']}\n"
            f"👥 Участников: 1/20\n\n"
            f"Теперь другие игроки могут присоединиться к вашему клану!",
            parse_mode="HTML",
            reply_markup=MAIN_KB
        )
    else:
        await msg.reply_text(
            "❌ Не удалось создать клан. Попробуйте ещё раз:",
            parse_mode="HTML"
        )

async def refresh_clan_message(query, player):
    """Обновляет сообщение с информацией о кланах"""
    if player.get("clan"):
        # Показать информацию о клане
        clan_name = player["clan"]
        if clan_name in clans:
            clan = clans[clan_name]
            text = (
                f"🏰 <b>Клан: {clan['name']}</b>\n\n"
                f"👑 Лидер: {players[clan['leader']]['name']}\n"
                f"👥 Участников: {len(clan['members'])}/20\n"
                f"📊 Уровень: {clan['level']}\n"
                f"⭐ XP: {clan['xp']}\n"
                f"📝 Описание: {clan['description']}\n\n"
            )
            
            if clan["leader"] == str(query.from_user.id):
                text += "👑 Вы лидер клана"
            else:
                text += "👤 Вы участник клана"
        else:
            text = "❌ Ошибка: клан не найден"
            player.pop("clan", None)  # Удаляем несуществующий клан
            save_players()
    else:
        # Показать список кланов
        if not clans:
            text = (
                "🏰 <b>Кланы:</b>\n\n"
                "Пока нет созданных кланов.\n"
                "Создайте свой клан!"
            )
        else:
            text = "🏰 <b>Доступные кланы:</b>\n\n"
            for clan_name, clan in clans.items():
                text += f"{clan['color']} <b>{clan['name']}</b>\n"
                text += f"👥 Участников: {len(clan['members'])}/20\n"
                text += f"👑 Лидер: {players[clan['leader']]['name']}\n\n"
    
    # Создаем клавиатуру с кнопками
    keyboard = build_clans_keyboard(player)
    
    await safe_edit_message_text(query, text, parse_mode="HTML", reply_markup=keyboard)

# ----------------------------- Бой: callback-и -------------------------------

async def battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "Сначала нажми /start")
        return
    
    p = players[uid]
    state = context.user_data.get("battle")
    if not state:
        await safe_edit_message_text(query, "Сейчас ты не в бою.")
        return

    enemy = state["enemy"]
    action = query.data # battle:attack | battle:ability | battle:potion | battle:run

    # Получаем характеристики с учетом бонусов питомцев
    stats_with_pets = get_player_stats_with_pets(p)

    log = ""
    if action == "battle:attack":
        dmg = dmg_roll(stats_with_pets["attack"], enemy["defense"])
        enemy["hp"] -= dmg
        log += f"Ты атаковал {enemy['name']} и нанёс {dmg} урона.\n"
    elif action == "battle:ability":
        if state.get("ability_used"):
            log += "Способность уже использована в этом бою!\n"
        else:
            cls = p["class"]
            if cls == "⚔️ Воин":
                dmg = dmg_roll(stats_with_pets["attack"], enemy["defense"]) * 2
                enemy["hp"] -= dmg
                log += f"Ты применил 'Мощный удар' и нанёс {dmg} урона!\n"
            elif cls == "🧙 Маг":
                dmg = 15
                enemy["hp"] -= dmg
                log += f"Ты применил 'Огненная вспышка' и нанёс {dmg} чистого урона!\n"
            elif cls == "🕵️ Вор":
                dmg = max(1, stats_with_pets["attack"] + random.randint(0, 2)) # игнор брони
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
        if random.random() < 0.6:
            await safe_edit_message_text(query, "Ты успешно сбежал с поля боя.")
            context.user_data.pop("battle", None)
            return
        else:
            log += "Не удалось сбежать!\n"

    # Проверка смерти врага
    if enemy["hp"] <= 0:
        loot_text = grant_rewards(p, enemy["xp"], enemy["gold"], enemy.get("loot"))
        quest_text = update_quests_on_enemy_kill(p, enemy.get("type", ""))

        await safe_edit_message_text(query, f"Ты победил {enemy['name']}! {loot_text}{quest_text}")
        context.user_data.pop("battle", None)
        return

    # Ход врага (если жив)
    if enemy["hp"] > 0 and action != "battle:run":
        edmg = dmg_roll(enemy["attack"], stats_with_pets["defense"])
        p["hp"] -= edmg
        save_players()
        log += f"{enemy['name']} атакует и наносит {edmg} урона.\n"

    # Проверка смерти игрока
    if p["hp"] <= 0:
        loss_gold = min(10, p["gold"])
        p["gold"] -= loss_gold
        p["hp"] = max(1, p["max_hp"] // 2)
        save_players()
        await safe_edit_message_text(
            query,
            f"Ты пал в бою... Потеряно {loss_gold} золота. "
            f"Ты приходишь в себя с {p['hp']}/{p['max_hp']} HP."
        )
        context.user_data.pop("battle", None)
        return

    # Обновляем текст боя
    try:
        await safe_edit_message_text(
            query,
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )
    except Exception:
        await query.message.reply_text(
            battle_text(p, enemy, log),
            reply_markup=build_battle_kb()
        )

# ----------------------------- Выбор класса/тексты ---------------------------

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user
    player = ensure_player(user.id, user.first_name or "Герой")

    state = context.user_data.get("state", "idle")

    # Проверяем, ожидаем ли мы ввод ставки для казино
    if context.user_data.get("awaiting_casino_bet"):
        await casino_bet_input(update, context)
        return

    # Проверяем, ожидаем ли мы ввод названия клана
    if context.user_data.get("clan_creation"):
        await handle_clan_creation(update, context)
        return
    
    # Проверяем, ожидаем ли мы ввод количества для массовой покупки
    if context.user_data.get("awaiting_bulk_amount"):
        await handle_bulk_purchase(update, context)
        return

    if state == "choose_class":
        choice = msg.text.strip()
        if choice in CLASS_STATS:
            set_class(player, choice)
            context.user_data["state"] = "idle"
            await msg.reply_text(
                f"🎉 <b>Отличный выбор!</b>\n\n"
                f"🎭 Класс: {choice}\n"
                f"💫 Способность: {ability_description(choice)}\n\n"
                f"🌟 Теперь вы можете:\n"
                f"🗺️ Отправиться в приключение\n"
                f"🎰 Играть в казино\n"
                f"🛒 Посетить магазин\n"
                f"🏆 Зарабатывать достижения\n"
                f"🐾 Собирать питомцев\n\n"
                f"🎮 Удачи в приключениях!",
                parse_mode="HTML",
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
        # Проверка активного боя или торговца
        if context.user_data.get("battle"):
            await msg.reply_text("⚠️ Сначала завершите текущий бой!", reply_markup=MAIN_KB)
            return
        if context.user_data.get("merchant_active"):
            await msg.reply_text("⚠️ Сначала завершите торговлю с купцом!", reply_markup=MAIN_KB)
            return
            
        await adventure_cmd(update, context)
    elif msg.text == "🧾 Квесты":
        await quests_cmd(update, context)
    elif msg.text == "🛒 Магазин":
        await shop_cmd(update, context)
    elif msg.text == "🎰 Казино":
        await casino_cmd(update, context)
    elif msg.text == "💸 Траты":
        await spend_cmd(update, context)
    elif msg.text == "⚙️ Помощь":
        await help_cmd(update, context)
    elif msg.text == "🏆 Достижения":
        await achievements_cmd(update, context)
    elif msg.text == "🎁 Ежедневные":
        await daily_cmd(update, context)
    elif msg.text == "🐾 Питомцы":
        await pets_cmd(update, context)
    elif msg.text == "💼 Бизнес":
        await businesses_cmd(update, context)
    elif msg.text == "🏰 Кланы":
        await clans_cmd(update, context)
    elif msg.text == "⚔️ PvP":
        await pvp_cmd(update, context)
    else:
        await msg.reply_text("Не понимаю. Используй кнопки или команды /help.", reply_markup=MAIN_KB)

async def handle_bulk_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка массовой покупки"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    item_name = context.user_data.get("bulk_buy_item")
    
    if not item_name or item_name not in SHOP_ITEMS:
        context.user_data.pop("bulk_buy_item", None)
        context.user_data.pop("awaiting_bulk_amount", None)
        await update.message.reply_text("❌ Ошибка: товар не найден", reply_markup=MAIN_KB)
        return
    
    try:
        amount = int(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Количество должно быть положительным")
    except ValueError:
        await update.message.reply_text("❌ Введите корректное количество (число больше 0)")
        return
    
    price = SHOP_ITEMS[item_name]["price"]
    total_cost = price * amount
    
    if p["gold"] < total_cost:
        max_affordable = p["gold"] // price
        await update.message.reply_text(
            f"❌ Недостаточно золота для покупки {amount} {item_name}.\n"
            f"Нужно {total_cost}💰, у вас {p['gold']}💰.\n"
            f"Максимум можете купить: {max_affordable} штук"
        )
        return
    
    # Выполняем покупку
    p["gold"] -= total_cost
    add_item(p, item_name, amount)
    
    emoji = SHOP_ITEMS[item_name].get("emoji", "📦")
    
    await update.message.reply_text(
        f"🛒 <b>Массовая покупка завершена!</b>\n\n"
        f"{emoji} Куплено: {item_name} x{amount}\n"
        f"💸 Потрачено: {total_cost}💰\n"
        f"💰 Текущий баланс: {p['gold']}💰",
        parse_mode="HTML",
        reply_markup=MAIN_KB
    )
    
    # Очищаем состояние
    context.user_data.pop("bulk_buy_item", None)
    context.user_data.pop("awaiting_bulk_amount", None)

def build_clans_keyboard(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Клавиатура для управления кланами"""
    keyboard = []
    
    if player.get("clan"):
        # Игрок уже в клане
        keyboard.append([InlineKeyboardButton("🚪 Покинуть клан", callback_data="clan:leave")])
    else:
        # Игрок не в клане
        keyboard.append([InlineKeyboardButton("🏗️ Создать клан", callback_data="clan:create")])
        
        # Кнопки для присоединения к существующим кланам
        available_clans = []
        player_id = str(next((k for k, v in players.items() if v is player), None) or "")
        for clan_name, clan in clans.items():
            if len(clan['members']) < 20 and player_id not in clan['members']:
                available_clans.append(clan_name)
        
        if available_clans:
            for clan_name in available_clans[:5]:  # Максимум 5 кнопок
                clan = clans[clan_name]
                keyboard.append([InlineKeyboardButton(
                    f"➕ Присоединиться к {clan['name']}",
                    callback_data=f"clan:join:{clan_name}"
                )])
    
    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data="clan:refresh")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="clan:main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def build_spend_kb(player: Dict[str, Any]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 Обучение (+80 XP) — 50💰", callback_data="spend:training")],
        [
            InlineKeyboardButton("⚒ Улучшить атаку (+1) — 100💰", callback_data="spend:up_atk"),
            InlineKeyboardButton("🛡 Улучшить защиту (+1) — 100💰", callback_data="spend:up_def"),
        ],
        [InlineKeyboardButton("🎁 Купить кейс — 120💰", callback_data="spend:lootbox")],
        [
            InlineKeyboardButton("🎗 Пожертвовать 25💰", callback_data="spend:donate:25"),
            InlineKeyboardButton("50💰", callback_data="spend:donate:50"),
            InlineKeyboardButton("100💰", callback_data="spend:donate:100"),
        ],
        [InlineKeyboardButton("🚪 Закрыть", callback_data="spend:close")],
    ])

async def spend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    await update.message.reply_text(
        "💸 Дополнительные способы потратить золото:\nВыберите действие:",
        reply_markup=build_spend_kb(p)
    )

async def spend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "Сначала нажми /start")
        return
    p = players[uid]
    data = query.data.split(":")  # spend:action[:amount]

    def not_enough(required: int):
        return (
            f"❌ Недостаточно золота.\n"
            f"Нужно {required}💰, у тебя {p['gold']}💰."
        )

    if data[1] == "close":
        await safe_edit_message_text(query, "Закрыто.")
        return

    if data[1] == "training":
        cost, xp_gain = 50, 80
        if p["gold"] < cost:
            await safe_edit_message_text(query, not_enough(cost), reply_markup=build_spend_kb(p))
            return
        p["gold"] -= cost
        p["xp"] += xp_gain
        save_players()
        await safe_edit_message_text(
            query,
            f"📘 Тренировка завершена: +{xp_gain} XP. Баланс: {p['gold']}💰",
            reply_markup=build_spend_kb(p)
        )
        return

    if data[1] == "up_atk":
        cost = 100
        if p["gold"] < cost:
            await safe_edit_message_text(query, not_enough(cost), reply_markup=build_spend_kb(p))
            return
        p["gold"] -= cost
        p["attack"] += 1
        save_players()
        await safe_edit_message_text(
            query,
            f"⚒ Атака увеличена на 1. Баланс: {p['gold']}💰",
            reply_markup=build_spend_kb(p)
        )
        return

    if data[1] == "up_def":
        cost = 100
        if p["gold"] < cost:
            await safe_edit_message_text(query, not_enough(cost), reply_markup=build_spend_kb(p))
            return
        p["gold"] -= cost
        p["defense"] += 1
        save_players()
        await safe_edit_message_text(
            query,
            f"🛡 Защита увеличена на 1. Баланс: {p['gold']}💰",
            reply_markup=build_spend_kb(p)
        )
        return

    if data[1] == "lootbox":
        cost = 120
        if p["gold"] < cost:
            await safe_edit_message_text(query, not_enough(cost), reply_markup=build_spend_kb(p))
            return
        p["gold"] -= cost
        reward_text = "Пустой кейс... невезёт!"
        # 10% шанс питомца, если есть доступные
        if random.random() < 0.10:
            available_pets = [pid for pid in PETS.keys() if pid not in p.get("pets", [])]
            if available_pets:
                pet_id = random.choice(available_pets)
                p.setdefault("pets", []).append(pet_id)
                reward_text = f"🐾 Питомец: {PETS[pet_id]['emoji']} {PETS[pet_id]['name']}"
        # Иначе предмет или золото
        if reward_text.startswith("Пустой"):
            candidates = ["Малое зелье лечения", "Руна силы", "Эликсир удачи", "Свиток телепортации"]
            if random.random() < 0.6:
                item = random.choice(candidates)
                add_item(p, item, 1)
                reward_text = f"🎒 Предмет: {item}"
            else:
                gold_gain = random.randint(50, 200)
                p["gold"] += gold_gain
                reward_text = f"💰 Возврат: +{gold_gain} золота"
        save_players()
        await safe_edit_message_text(
            query,
            f"🎁 Кейс открыт! {reward_text}\nТекущий баланс: {p['gold']}💰",
            reply_markup=build_spend_kb(p)
        )
        return

    if data[1] == "donate":
        if len(data) < 3:
            await query.answer("Ошибка доната", show_alert=True)
            return
        amount = int(data[2])
        if p["gold"] < amount:
            await safe_edit_message_text(query, not_enough(amount), reply_markup=build_spend_kb(p))
            return
        p["gold"] -= amount
        xp_gain = amount // 2
        p["xp"] += xp_gain
        save_players()
        await safe_edit_message_text(
            query,
            f"🎗 Спасибо за щедрость! Потрачено {amount}💰, получено +{xp_gain} XP.\nБаланс: {p['gold']}💰",
            reply_markup=build_spend_kb(p)
        )
        return

async def quest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок квестов"""
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    if uid not in players:
        await safe_edit_message_text(query, "❌ Сначала начните игру (/start)")
        return
    
    p = players[uid]
    data = query.data.split(":")
    
    if data[1] == "close":
        await safe_edit_message_text(query, "Закрыто.")
        return
    
    elif data[1] == "refresh":
        await quests_cmd(update, context)
        return
    
    elif data[1] == "new":
        # Проверяем количество активных квестов
        active_quests = sum(1 for q in p["quests"].values() if q.get("status") == "active")
        if active_quests >= 3:
            await query.answer("❌ У вас уже максимальное количество активных квестов (3)", show_alert=True)
            return
        
        # Генерируем новый квест
        new_quest = generate_random_quest(p["level"])
        quest_id = f"random_quest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        p["quests"][quest_id] = {
            **new_quest,
            "progress": 0,
            "status": "active"
        }
        save_players()
        
        await query.answer(f"🎯 Новый квест получен: {new_quest['title']}", show_alert=True)
        await quests_cmd(update, context)
        return

# --------------------------------- Main --------------------------------------

def main():
    load_players()
    load_clans()
    app = ApplicationBuilder().token("YOUR_TOKEN_BOT").build()

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("use_potion", use_potion_cmd))
    app.add_handler(CommandHandler("quests", quests_cmd))
    app.add_handler(CommandHandler("adventure", adventure_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("casino", casino_cmd))
    app.add_handler(CommandHandler("achievements", achievements_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("pets", pets_cmd))
    app.add_handler(CommandHandler("clans", clans_cmd))
    app.add_handler(CommandHandler("pvp", pvp_cmd))
    app.add_handler(CommandHandler("pvp_challenge", pvp_challenge_cmd))
    app.add_handler(CommandHandler("business", businesses_cmd))
    app.add_handler(CommandHandler("spend", spend_cmd))
    
    # Обработчики callback'ов
    app.add_handler(CallbackQueryHandler(battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(casino_callback, pattern=r"^casino:"))
    app.add_handler(CallbackQueryHandler(clan_callback, pattern=r"^clan:"))
    app.add_handler(CallbackQueryHandler(businesses_callback, pattern=r"^biz:"))
    app.add_handler(CallbackQueryHandler(spend_callback, pattern=r"^spend:"))
    app.add_handler(CallbackQueryHandler(quest_callback, pattern=r"^quest:"))
    app.add_handler(CallbackQueryHandler(pvp_callback, pattern=r"^pvp:"))
    
    # Обработчик текстовых сообщений (включая ставки для казино)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
