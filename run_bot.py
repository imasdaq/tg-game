import os
import subprocess

def main():
    # Проверяем токен
    token = os.getenv('BOT_TOKEN')
    if not token:
        print('❌ Ошибка: BOT_TOKEN не установлен')
        exit(1)
    
    print('🔧 Заменяем токен...')
    
    # Читаем основной файл
    with open('gamecode_ru.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем токен
    content = content.replace('"YOUR_TOKEN_BOT"', f'"{token}"')
    
    # Записываем временный файл
    with open('gamecode_temp.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('🚀 Запускаем бота...')
    
    # Запускаем основной скрипт
    exec(open('gamecode_temp.py').read())

if __name__ == '__main__':
    main()
