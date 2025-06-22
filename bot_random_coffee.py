#Реализация функции RandonCoffee - подбор собеседника среди абитуриентов
import schedule
import time
from datetime import datetime, timedelta
import random
import mysql.connector
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import os

from db import connect_db

load_dotenv("config.env")  # Загружает переменные из config.env
STICKERS_RANDOM_COFFEE = [
"CAACAgIAAxkBAAIGb2g0TztSdWZO6rni7C8OQZWn59NOAAIheQAC136ZSWt9_w0gh9vZNgQ",  
"CAACAgIAAxkBAAIGbGg0TuSO0aNPWvKm60Bwiw9NULOEAAJtdgACpr6hSXy4hRKdMQ4ONgQ"]
def random_coffee(bot, show_main_menu):
    user_states_random_coffee = {}
    # --- Обработка нажатий на кнопки ---
    @bot.message_handler(func=lambda message: message.text in ["Конечно💜", "Не сейчас"])
    def handle_participation(message):
        user_id = message.from_user.id
        if message.text == "Конечно💜":
            actual_flag = True
            bot.send_message(user_id, "Отлично! Вернусь в следующий четверг😌")
        else:
            actual_flag = False
            bot.send_message(user_id, "Буду ждать тебя в следующий раз🙂")
    
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users_random_coffee SET actual = %s WHERE user_id = %s", (actual_flag, user_id))
        conn.commit()
        cursor.close()
        conn.close()
    #Регистрация пользователя    
    @bot.message_handler(func=lambda message: message.text == "Random Coffee")
    def ask_interest(message):
        chat_id = message.chat.id
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users_random_coffee WHERE user_id = %s", (chat_id,))
        exists = cur.fetchone() is not None
        if exists:
            cur.execute("UPDATE users_random_coffee SET actual = TRUE WHERE user_id = %s", (chat_id,))
            conn.commit()
            cur.close()
            conn.close()
            user_states_random_coffee[chat_id] = {"stage": "menu"}
            handle_state(message) 
        else:
            cur.close()
            conn.close()
            user_states_random_coffee[chat_id] = {"stage": "auth"}  
            bot.send_message(chat_id, "Хочешь понетворкать? Введи код авторизации (код авторизации: 11111)")

    @bot.message_handler(func=lambda message: message.chat.id in user_states_random_coffee and message.text in [
    "Изменить описание",
    "Отказаться от нетворкинга",
    "Вернуться в главное меню"
] or user_states_random_coffee.get(message.chat.id, {}).get("stage") in ["info_1"])
    def handle_state(message):
        chat_id = message.chat.id
        state = user_states_random_coffee[chat_id]
    
        if message.text == "Изменить описание":
            user_states_random_coffee[chat_id] = {"stage": "info_1"}
            bot.send_message(chat_id, "Расскажи о себе")
            return
    
        elif message.text == "Отказаться от нетворкинга":
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users_random_coffee WHERE user_id = %s", (chat_id,))
            conn.commit()
            cursor.close()
            conn.close()
            user_states_random_coffee.pop(chat_id, None)
            bot.send_message(chat_id, "Хорошо, можешь вернуться в любой момент🙂 \nЯ буду тебя ждать и очень скучать")
            bot.send_sticker(chat_id, "CAACAgIAAxkBAAIGdGg0T9VTm9UmuNASzZuBAakt1KoCAAJzdQACmWihSdo0w9rBPpimNgQ")
            show_main_menu(chat_id)
            return
    
        elif message.text == "Вернуться в главное меню":
            user_states_random_coffee.pop(chat_id, None)
            show_main_menu(chat_id)
            return
    
        if state["stage"] == "menu":
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(
                types.KeyboardButton("Изменить описание"),
                types.KeyboardButton("Отказаться от нетворкинга"),
                types.KeyboardButton("Вернуться в главное меню")
            )
            bot.send_message(chat_id, "Уже ищу кого-то для тебя☺️\nВернусь в четверг", reply_markup=keyboard)
            user_states_random_coffee[chat_id] = {"stage": "good"}
            return
    
        # Проверка кода доступа (можно заменить на авторизацию через личный кабинет или телеграм, требуется в качестве меры безопасности для абитуриентов)
        if state["stage"] == "auth":
            if message.text.strip() == "11111":
                conn = connect_db()
                cur = conn.cursor()
                cur.execute("SELECT telegram_name FROM users WHERE id = %s", (chat_id,))
                result = cur.fetchone()
                cur.close()
                conn.close()
    
                if result and result[0]:
                    telegram_name = result[0]
                    user_states_random_coffee[chat_id]["telegram_name"] = telegram_name
                    user_states_random_coffee[chat_id]["stage"] = "confirm_username"
    
                    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                    keyboard.add(
                        types.KeyboardButton("Да"),
                        types.KeyboardButton("Нет")
                    )
                    bot.send_message(chat_id, f"Твой ник в Telegram: {telegram_name}\nВсё верно?", reply_markup=keyboard)
                else:
                    bot.send_message(chat_id, "Мы не нашли твой ник в системе. Введи, пожалуйста, свой ник (например, @username):")
                    user_states_random_coffee[chat_id]["stage"] = "get_username"
            else:
                bot.send_message(chat_id, "Неверный код. Попробуй ещё раз")
    
        # Подтверждение ника в телеграм
        elif state["stage"] == "confirm_username":
            if message.text == "Да":
                bot.send_message(chat_id, "Теперь расскажи немного о себе :)")
                user_states_random_coffee[chat_id]["stage"] = "info_1"
            elif message.text == "Нет":
                bot.send_message(chat_id, "Введи, пожалуйста, свой ник в Telegram (например, @username):")
                user_states_random_coffee[chat_id]["stage"] = "get_username"
            else:
                bot.send_message(chat_id, "Пожалуйста, нажми кнопку 'Да' или 'Нет'.")
    
        # Ввод Telegram ника вручную
        elif state["stage"] == "get_username":
            telegram_name = message.text.strip()
            if not telegram_name.startswith("@"):
                telegram_name = "@" + telegram_name
            user_states_random_coffee[chat_id]["telegram_name"] = telegram_name
            user_states_random_coffee[chat_id]["stage"] = "info_1"
            bot.send_message(chat_id, "Теперь расскажи немного о себе :)")
    
        # Ввод описания
        elif state["stage"] == "info_1":
            info = message.text.strip()
            telegram_name = user_states_random_coffee[chat_id].get("telegram_name", "")
    
            conn = connect_db()
            cur = conn.cursor()
    
            query = """
            INSERT INTO users_random_coffee (user_id, telegram_name, user_info, joined_at, actual, is_new)
            VALUES (%s, %s, %s, NOW(), TRUE, TRUE)
            ON DUPLICATE KEY UPDATE
            telegram_name = VALUES(telegram_name),
            user_info = VALUES(user_info),
            actual = TRUE,
            joined_at = NOW(),
            is_new = FALSE
            """
    
            cur.execute(query, (chat_id, telegram_name, info))
            conn.commit()
            cur.close()
            conn.close()
    
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(
                types.KeyboardButton("Изменить описание"),
                types.KeyboardButton("Отказаться от нетворкинга"),
                types.KeyboardButton("Вернуться в главное меню")
            )
    
            bot.send_message(chat_id, "Подбираю собеседника. Вернусь в четверг, до встречи 👋", reply_markup=keyboard)
            user_states_random_coffee[chat_id] = {"stage": "menu"}
            show_main_menu(chat_id)

    @bot.callback_query_handler(func=lambda call: call.data in ["confirm_username_yes", "confirm_username_no"])
    def handle_username_confirmation(call):
        chat_id = call.message.chat.id
    
        if call.data == "confirm_username_yes":
            bot.answer_callback_query(call.id, "Отлично!")
            bot.send_message(chat_id, "Теперь расскажи немного о себе :)")
            user_states_random_coffee[chat_id]["stage"] = "info_1"
        else:
            bot.answer_callback_query(call.id, "Хорошо, давай введём заново")
            bot.send_message(chat_id, "Введи, пожалуйста, свой ник в Telegram (например, @username):")
            user_states_random_coffee[chat_id]["stage"] = "get_username"
            # подтверждение ника

    # --- Функция для обновления actual в четверг в 17:00 ---
    def update_actual_flag():
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users_random_coffee SET actual = FALSE, is_new = FALSE")
        conn.commit()
        cursor.close()
        conn.close()
        print("[RandomCoffee] Флаги actual сброшены")
    
    # --- Функция для формирования пар в четверг в 18:30 ---
    def form_pairs_and_notify():
        conn = connect_db()
        cursor = conn.cursor()
    
        # Получаем список участников, у которых actual = TRUE
        cursor.execute("SELECT user_id, telegram_name, user_info FROM users_random_coffee WHERE actual = TRUE")
        users = cursor.fetchall()
    
        if len(users) < 2:
            print("[RandomCoffee] Недостаточно участников для формирования пар")
            cursor.close()
            conn.close()
            return
    
        # Перемешиваем пользователей
        random.shuffle(users)
        used_users = set()
        pairs = []
    
        for i in range(len(users)):
            user1 = users[i]
            if user1[0] in used_users:
                continue
    
            for j in range(i + 1, len(users)):
                user2 = users[j]
                if user2[0] in used_users:
                    continue
    
                # Проверка существующей пары (в любом порядке)
                user_ids_sorted = sorted([user1[0], user2[0]])
                cursor.execute("""
                    SELECT 1 FROM random_coffee_matches
                    WHERE (user1_id = %s AND user2_id = %s)
                       OR (user1_id = %s AND user2_id = %s)
                """, (user_ids_sorted[0], user_ids_sorted[1], user_ids_sorted[1], user_ids_sorted[0]))
    
                if cursor.fetchone() is None:
                    pairs.append((user1, user2))
                    used_users.add(user1[0])
                    used_users.add(user2[0])
                    break  # нашли пару — переходим к следующему пользователю
    
        # Проверка: остались ли участники без пары
        remaining_users = [user for user in users if user[0] not in used_users]
        for u in remaining_users:
            print(f"[RandomCoffee] Пользователь {u[0]} без пары на этой неделе")
    
        # Отправляем сообщения и сохраняем пары
        for (user1, user2) in pairs:
            user1_id, user1_name, user1_info = user1
            user2_id, user2_name, user2_info = user2
    
            # Сохраняем пару
            cursor.execute("""
                INSERT INTO random_coffee_matches (user1_id, user2_id, matched_at)
                VALUES (%s, %s, NOW())
            """, (user1_id, user2_id))
    
            try:
                bot.send_message(user1_id, f"Твой собеседник на этой неделе: {user2_name}\n\nОписание: {user2_info}")
                maybe_send_sticker(user1_id)
                show_main_menu(user1_id)
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user1_id}: {e}")
    
            try:
                bot.send_message(user2_id, f"Твой собеседник на этой неделе: {user1_name}\n\nОписание: {user1_info}")
                maybe_send_sticker(user2_id)
                show_main_menu(user2_id)
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user2_id}: {e}")
    
        conn.commit()
        cursor.close()
        conn.close()
    
        print("[RandomCoffee] Пары сформированы и уведомления отправлены")

    
    # Функция для рассылки в понедельник с кнопками
    def send_monday_invites():
        print("== send_monday_invites called ==") 
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""SELECT user_id FROM users_random_coffee
        WHERE is_new = FALSE""")
        all_users = cursor.fetchall()
    
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(
            types.KeyboardButton("Конечно💜"),
            types.KeyboardButton("Не сейчас")
        )
    
        for (user_id,) in all_users:
            try:
                bot.send_message(user_id, "Хочешь познакомиться еще с кем-нибудь?", reply_markup=keyboard)
            except Exception as e:
                print(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
    
        cursor.close()
        conn.close()
    # Отправка стикера пользователю
    def maybe_send_sticker(user_id):
        choices = STICKERS_RANDOM_COFFEE + [None]  
        sticker = random.choice(choices)
        if sticker:
            try:
                bot.send_sticker(user_id, sticker)
            except Exception as e:
                print(f"Ошибка при отправке стикера пользователю {user_id}: {e}")
                
    schedule.every().thursday.at("17:00").do(update_actual_flag)
    schedule.every().thursday.at("18:30").do(form_pairs_and_notify)
    schedule.every().monday.at("11:00").do(send_monday_invites)
    
    import threading
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    threading.Thread(target=run_scheduler, daemon=True).start()