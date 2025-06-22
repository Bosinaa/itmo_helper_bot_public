import telebot
from telebot import types
import mysql.connector
from dotenv import load_dotenv
import os
load_dotenv("config.env")  # Загружает переменные из config.env

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

from db import connect_db # Подключение к бд
from bot_random_coffee import random_coffee # Random Coffee
from bot_feedback import feedback # Обратная связь
from bot_programs_search import program_tasks # Поиск наиболее подходящей образовательной программы
from bot_dates import important_dates # Важные даты
from bot_llm_task import llm_tasks # Ответы на вопросы

user_data = {}
def get_user_from_db(user_id):
    try:
        conn = connect_db()
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"DB error: {e}")
    finally:
        if conn:
            conn.close()

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.chat.id
    user = get_user_from_db(user_id)

    if user:
        name = user[0]
        bot.send_message(user_id, f"Привет, {name}! Рад снова тебя видеть 👋")
        show_main_menu(user_id)
    else:
        bot.send_message(user_id, "Привет! Как тебя зовут?")
        user_data[user_id] = {'step': 'waiting_for_name'}

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'waiting_for_name')
def get_name(message):
    user_id = message.chat.id
    name = message.text.strip()
    user_data[user_id]['name'] = name

    username = message.from_user.username
    if not username:
        bot.send_message(user_id, "У тебя не указан Telegram username. Введи, пожалуйста, свой ник (например, @yourname):")
        user_data[user_id]['step'] = 'waiting_for_manual_telegram'
    else:
        user_data[user_id]['telegram_candidate'] = f"@{username}"
        user_data[user_id]['step'] = 'waiting_for_telegram_confirmation'
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(KeyboardButton("Да"), KeyboardButton("Нет"))
        bot.send_message(user_id, f"Это твой Telegram: @{username}?", reply_markup=markup)

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'waiting_for_telegram_confirmation')
def handle_telegram_confirmation(message):
    user_id = message.chat.id
    answer = message.text.strip().lower()

    if answer == "да":
        user_data[user_id]['telegram'] = user_data[user_id]['telegram_candidate']
        finalize_user_setup(user_id)
    elif answer == "нет":
        user_data[user_id]['step'] = 'waiting_for_manual_telegram'
        bot.send_message(user_id, "Хорошо, введи свой Telegram ник (например, @yourname):")
    else:
        bot.send_message(user_id, "Пожалуйста, выбери «Да» или «Нет»")

@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('step') == 'waiting_for_manual_telegram')
def handle_manual_telegram(message):
    user_id = message.chat.id
    telegram_input = message.text.strip()
    if not telegram_input.startswith("@"):
        telegram_input = "@" + telegram_input

    user_data[user_id]['telegram'] = telegram_input
    finalize_user_setup(user_id)
    
# Завершение регистрации 
def finalize_user_setup(user_id):
    name = user_data[user_id]['name']
    telegram = user_data[user_id]['telegram']
    bot.send_message(user_id, f"Спасибо, {name}! Я готов помочь с поступлением в магистратуру 🎓")
    show_main_menu(user_id)
    save_user_to_db(user_id, name, telegram)
    user_data[user_id]['step'] = 'done'
    
# Главное меню бота    
def show_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Выбрать магистратуру")
    btn2 = types.KeyboardButton("Важные даты")
    btn3 = types.KeyboardButton("Задать вопрос 💙")
    btn4 = types.KeyboardButton("Random Coffee")
    btn5 = types.KeyboardButton("Передать привет разработчикам (или сообщить о баге)")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)

    bot.send_message(chat_id, "Чем хочешь заняться?", reply_markup=markup)

# Сохранение данных пользователя в бд 
def save_user_to_db(user_id, name, telegram_name):
    conn = connect_db()
    cursor = conn.cursor()
    query = """
    INSERT INTO users (id, username, telegram_name)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE username = VALUES(username), telegram_name = VALUES(telegram_name)
    """
    cursor.execute(query, (user_id, name, telegram_name))
    conn.commit()
    cursor.close()
    conn.close()

feedback(bot, show_main_menu) 
program_tasks(bot, show_main_menu)
important_dates(bot, show_main_menu)
random_coffee(bot, show_main_menu)
llm_tasks(bot, show_main_menu)

bot.polling()