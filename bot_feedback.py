# Отправка обратной связи разработчику
from telebot import types
import mysql.connector
import random
from dotenv import load_dotenv
import os
load_dotenv("config.env")  # Загружает переменные из config.env
from db import connect_db

FEEDBACK_STICKERS = ["CAACAgIAAxkBAAIGdmg0T_QpKJfgNbI67_hG7XIPF2zfAALYYgACBZOhSaeRjMJjeOnWNgQ",  
    "CAACAgIAAxkBAAIGcWg0T7FPZoJ1j5D3BSGjNyUbNnC6AAK-cQACI-qhSVRBXzJtety5NgQ"]
def feedback(bot, show_main_menu):
    user_state_feedback = {}

    def maybe_send_sticker(chat_id):
        choices = FEEDBACK_STICKERS + [None]  # два стикера + пустой вариант
        sticker = random.choice(choices)
        if sticker:
            try:
                bot.send_sticker(chat_id, sticker)
            except Exception as e:
                print(f"Ошибка при отправке стикера пользователю {chat_id}: {e}")
    # Сохранение отзыва в БД
    def save_feedback_to_db(user_id, info):
        conn = connect_db()
        cursor = conn.cursor()
        query = "INSERT INTO user_feedback (user_id, info) VALUES (%s, %s)"
        cursor.execute(query, (user_id, info))
        conn.commit()
        cursor.close()
        conn.close()
        
    # === Хендлеры ===
    # Хендлер запускается, когда пользователь хочет оставить отзыв
    @bot.message_handler(func=lambda message: message.text == "Передать привет разработчикам (или сообщить о баге)")
    def ask_interest(message):
        chat_id = message.chat.id
        user_state_feedback[message.chat.id] = {'step': 'waiting_for_feedback'}
        bot.send_message(chat_id, "Привет! Оставь отзыв о боте или расскажи, если нашел ошибку")
    # Обработка текста отзыва
    @bot.message_handler(func=lambda message: user_state_feedback.get(message.chat.id, {}).get('step') == 'waiting_for_feedback')
    def handle_feedback(message):
        chat_id = message.chat.id
        feedback_text = message.text.strip()
        save_feedback_to_db(chat_id, feedback_text)
        bot.send_message(chat_id, "Спасибо за отзыв! Он поможет сделать бота лучше")
        maybe_send_sticker(chat_id)
        # Сброс состояния и возвращение в главное меню
        user_state_feedback.pop(chat_id, None)
        show_main_menu(chat_id)
        

    