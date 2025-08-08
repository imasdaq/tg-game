# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
import os
import random
from typing import Dict, Any, Optional, List

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
    [["🗺️ Приключение", "📊 Статус"], 
     ["🎒 Инвентарь", "🧾 Квесты"], 
     ["🛒 Магазин", "🎰 Казино"],
     ["🏆 Достижения", "🎁 Ежедневные"],
     ["⚔️ PvP", "🏰 Кланы"],
     ["🐾 Питомцы", "⚙️ Помощь"]],
    resize_keyboard=True
)

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
    
    elif action == "clan_created" and "clan_leader" not in player["achievements"]:
        player["achievements"]["clan_leader"] = {"earned": True, "date": datetime.now().isoformat()}
        earned.append("clan_leader")
    
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

def build_shop_kb() -> InlineKeyboardMarkup:
    buttons = []
    for item_name, meta in SHOP_ITEMS.items():
        emoji = meta.get("emoji", "📦")
        buttons.append([InlineKeyboardButton(f"{emoji} Купить: {item_name} ({meta['price']}💰)", callback_data=f"shop:buy:{item_name}")])
    buttons.append([InlineKeyboardButton("Закрыть", callback_data="shop:close")])
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
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(CASINO_GAMES["double"]["name"], callback_data="casino:double"),
         InlineKeyboardButton(CASINO_GAMES["dice"]["name"], callback_data="casino:dice")],
        [InlineKeyboardButton(CASINO_GAMES["roulette"]["name"], callback_data="casino:roulette"),
         InlineKeyboardButton(CASINO_GAMES["slots"]["name"], callback_data="casino:slots")],
        [InlineKeyboardButton(CASINO_GAMES["blackjack"]["name"], callback_data="casino:blackjack")],
        [InlineKeyboardButton("🔁 Сменить ставку", callback_data="casino:change_bet")],
        [InlineKeyboardButton("❌ Отмена", callback_data="casino:exit")],
    ])

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
            return {"success": True, "message": f"🃏 Блэкджек! Выиграли {prize} золота!"}
        elif player_sum > 21:
            return {"success": False, "message": f"🃏 Перебор! Проиграли {bet} золота."}
        elif dealer_sum > 21 or player_sum > dealer_sum:
            prize = int(bet * game["multiplier"])
            player["gold"] += prize
            check_achievements(player, "casino_win")
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
        "/help - Показать это сообщение"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    
    # Поля уже инициализированы в migrate_player_data()
    
    # Получаем характеристики с учетом бонусов питомцев
    stats_with_pets = get_player_stats_with_pets(p)
    pet_bonuses = get_pet_bonuses(p)
    
    text = (
        f"📊 <b>Статус {p['name']} ({p['class'] or 'Без класса'})</b>\n\n"
        f"⚔️ Уровень: <b>{p['level']}</b> ({p['xp']}/{get_xp_to_next(p['level'])} XP)\n"
        f"❤️ HP: <b>{stats_with_pets['hp']}/{stats_with_pets['max_hp']}</b>\n"
        f"🗡️ Атака: <b>{stats_with_pets['attack']}</b> 🛡️ Защита: <b>{stats_with_pets['defense']}</b>\n"
        f"💰 Золото: <b>{p['gold']}</b>\n"
        f"🍀 Удача: <b>{stats_with_pets['luck']}</b>\n\n"
    )
    
    if pet_bonuses["attack"] > 0 or pet_bonuses["defense"] > 0 or pet_bonuses["hp"] > 0:
        text += "🐾 <b>Бонусы питомцев:</b>\n"
        if pet_bonuses["attack"] > 0:
            text += f"🗡️ Атака +{pet_bonuses['attack']}\n"
        if pet_bonuses["defense"] > 0:
            text += f"🛡️ Защита +{pet_bonuses['defense']}\n"
        if pet_bonuses["hp"] > 0:
            text += f"❤️ HP +{pet_bonuses['hp']}\n"
        text += "\n"
    
    if p.get("clan"):
        text += f"🏰 Клан: <b>{p['clan']}</b>\n"
    
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
    """Ежедневные награды"""
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    p = players[uid]
    
    # Поля уже инициализированы в migrate_player_data()
    
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
                text += "👑 Вы лидер клана\n"
                text += "Используйте /clan_leave чтобы покинуть клан"
            else:
                text += "👤 Вы участник клана\n"
                text += "Используйте /clan_leave чтобы покинуть клан"
        else:
            text = "❌ Ошибка: клан не найден"
    else:
        # Показать список кланов
        if not clans:
            text = (
                "🏰 <b>Кланы:</b>\n\n"
                "Пока нет созданных кланов.\n"
                "Используйте /clan_create [название] чтобы создать клан!"
            )
        else:
            text = "🏰 <b>Доступные кланы:</b>\n\n"
            for clan_name, clan in clans.items():
                text += f"{clan['color']} <b>{clan['name']}</b>\n"
                text += f"👥 Участников: {len(clan['members'])}/20\n"
                text += f"👑 Лидер: {players[clan['leader']]['name']}\n\n"
    
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_KB)

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
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    p = players[uid]
    q = p["quests"]
    if not q:
        await update.message.reply_text("📜 У тебя пока нет квестов.", reply_markup=MAIN_KB)
        return
    
    quests_text = []
    for quest in q.values():
        status = "✅" if quest["status"] == "completed" else "⌛"
        quests_text.append(
            f"{status} <b>{quest['title']}</b>\n"
            f"{quest['desc']}\n"
            f"Прогресс: {quest['progress']}/{quest['required']}\n"
        )
    
    await update.message.reply_text(
        "📜 <b>Активные квесты:</b>\n\n" + "\n".join(quests_text),
        parse_mode="HTML",
        reply_markup=MAIN_KB
    )

async def adventure_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in players:
        await update.message.reply_text("Сначала нажми /start")
        return
    
    # Проверка активного боя или торговца
    if context.user_data.get("battle") or context.user_data.get("merchant_active"):
        await update.message.reply_text(
            "⚠️ Сначала завершите текущее событие (бой или торговлю)!",
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
        context.user_data.pop("merchant_active", None)
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
        emoji = SHOP_ITEMS[item_name].get("emoji", "📦")
        
        if SHOP_ITEMS[item_name]["type"] == "consumable":
            add_item(p, item_name, 1)
            await query.edit_message_text(
                f"{emoji} Ты купил: {item_name}. В инвентаре пополнение! Золото: {p['gold']}.",
                reply_markup=build_shop_kb()  # Оставляем магазин открытым
            )
        elif SHOP_ITEMS[item_name]["type"] == "equipment":
            # Применяем эффекты экипировки
            if "attack_plus" in effect:
                p["attack"] += effect["attack_plus"]
            if "defense_plus" in effect:
                p["defense"] += effect["defense_plus"]
            if "luck_plus" in effect:
                p["luck"] = p.get("luck", 0) + effect["luck_plus"]
            save_players()
            await query.edit_message_text(
                f"{emoji} Ты купил и экипировал: {item_name}. Твоя сила растёт! Золото: {p['gold']}.",
                reply_markup=build_shop_kb()  # Оставляем магазин открытым
            )

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
    """Обработчик inline-кнопок казино"""
    query = update.callback_query
    await query.answer()
    
    uid = str(query.from_user.id)
    if uid not in players:
        await query.edit_message_text("❌ Сначала начните игру (/start)")
        return
    
    p = players[uid]
    data = query.data.split(":")
    
    if data[1] == "exit":
        context.user_data.pop("casino_bet", None)
        context.user_data.pop("awaiting_casino_bet", None)
        await query.edit_message_text("🚪 Вы покинули казино. Удачи в приключениях!")
        return
    elif data[1] == "change_bet":
        context.user_data.pop("casino_bet", None)
        context.user_data["awaiting_casino_bet"] = True
        await query.edit_message_text(
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
    save_players()
    
    if "Подождите" in result["message"]:
        await query.answer(result["message"], show_alert=True)
        return
    
    # Формируем полное сообщение с результатом
    message = (
        f"🎰 <b>{CASINO_GAMES[game_type]['name']}</b>\n"
        f"💵 Ставка: <b>{bet}</b> золота\n\n"
        f"{result['message']}\n\n"
        f"💰 Текущий баланс: <b>{p['gold']}</b> золота\n\n"
    )
    
    if result["success"] is False:
        message += "😔 Не повезло... Попробуйте ещё раз!"
    elif result["success"] is True:
        message += "🎉 Отличный результат! Хотите сыграть ещё?"
    else:
        message += "🤝 Ничья! Попробуйте ещё раз."
    
    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=build_casino_games_kb()
    )

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
            await query.edit_message_text("Ты успешно сбежал с поля боя.")
            context.user_data.pop("battle", None)
            return
        else:
            log += "Не удалось сбежать!\n"

    # Проверка смерти врага
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
                quest_text = f"\n✅ Квест '{q['title']}' выполнен! {add_text}"
            save_players()
        else:
            quest_text = f"\nКвест '{q['title']}': прогресс {q['progress']}/{q['required']}."
            save_players()

        await query.edit_message_text(
            f"Ты победил {enemy['name']}! {loot_text}{quest_text}"
        )
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
        await query.edit_message_text(
            f"Ты пал в бою... Потеряно {loss_gold} золота. "
            f"Ты приходишь в себя с {p['hp']}/{p['max_hp']} HP."
        )
        context.user_data.pop("battle", None)
        return

    # Обновляем текст боя
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
    elif msg.text == "⚙️ Помощь":
        await help_cmd(update, context)
    elif msg.text == "🏆 Достижения":
        await achievements_cmd(update, context)
    elif msg.text == "🎁 Ежедневные":
        await daily_cmd(update, context)
    elif msg.text == "🐾 Питомцы":
        await pets_cmd(update, context)
    elif msg.text == "🏰 Кланы":
        await clans_cmd(update, context)
    elif msg.text == "⚔️ PvP":
        await pvp_cmd(update, context)
    else:
        await msg.reply_text("Не понимаю. Используй кнопки или команды /help.", reply_markup=MAIN_KB)

# --------------------------------- Main --------------------------------------

def main():
    load_players()
    load_clans()
    app = ApplicationBuilder().token("8261910418:AAE9SWq5uITIIxCgzB8-1f2h-EibNufdk3s").build()

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
    
    # Обработчики callback'ов
    app.add_handler(CallbackQueryHandler(battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(casino_callback, pattern=r"^casino:"))
    
    # Обработчик текстовых сообщений (включая ставки для казино)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
