#!/bin/bash

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ Ошибка: BOT_TOKEN не установлен"
    exit 1
fi

echo "🔧 Заменяем токен во всех файлах..."

# Заменяем в gamecode_ru.py
sed "s/\"YOUR_TOKEN_BOT\"/\"$BOT_TOKEN\"/g" gamecode_ru.py > gamecode_temp.py

echo "🚀 Запускаем бота..."
python3 gamecode_temp.py

# Очистка при завершении
rm -f gamecode_temp.py