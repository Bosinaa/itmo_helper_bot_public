#отправка напоминаний о важных датах
from telebot import types
import mysql.connector
import random
import pymysql
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv("config.env") # Загружаем переменные окружения из файла
import os

def important_dates(bot, show_main_menu):
    def connect_db_0():
        return pymysql.connect(
            host=os.getenv("db_host"),
            user=os.getenv("db_user"),
            password=os.getenv("db_password"),
            database=os.getenv("db_name"),
            charset='utf8mb4',
            #port = "3306",
            cursorclass=pymysql.cursors.DictCursor 
        )
    # Получение всех ближайших событий (на завтра и через неделю) для всех заинтересованных пользователей
    # Определение топ-3 интересов пользователя по лайкам и количеству заданных вопросов
    def fetch_upcoming_events():
        conn = connect_db_0()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT pe.program_name, pe.event_name, pe.event_date, pe.description, upi.user_id
                    FROM program_events pe
                    JOIN user_program_interest upi ON pe.program_name = upi.program_name
                    WHERE 
                        (DATE(pe.event_date) = CURDATE() + INTERVAL 1 DAY OR DATE(pe.event_date) = CURDATE() + INTERVAL 7 DAY)
                        AND (
                            upi.liked = 1
                            OR upi.program_name IN (
                                SELECT program_name FROM (
                                    SELECT program_name
                                    FROM user_program_interest
                                    WHERE user_id = upi.user_id
                                    ORDER BY questions_count DESC
                                    LIMIT 3
                                ) AS top_programs
                            )
                        );
                """
                cursor.execute(sql)
                # Получаем результаты как словари (благодаря cursorclass=DictCursor)
                return cursor.fetchall()
        finally:
            conn.close()
    # Отправка напоминаний пользователям о событиях, если они заинтересованы в программе
    def send_event_reminders():
        events = fetch_upcoming_events()
        
        for event in events:
            try:
                if not isinstance(event, dict):
                    continue
                    
                user_id = event['user_id']
                event_name = event['event_name']
                program_name = event['program_name']
                event_date = event['event_date'].strftime('%d.%m.%Y')
                description = event['description']
    
                message = (
                    f"📅 Напоминаю: *{event_name}*\n по программе *{program_name}* "
                    f"пройдёт {event_date}.\n\n{description}"
                )
                
                bot.send_message(user_id, message, parse_mode='Markdown')
                
            except Exception as e:
                print(f"⛔ Ошибка при обработке события: {e}")
                
    # Планирование ежедневной рассылки в 11:00 по времени сервера
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_event_reminders, 'cron', hour=11, minute=00)
    scheduler.start()
    # === Хендлеры ===
    @bot.message_handler(func=lambda message: message.text == "Важные даты")
    def handle_important_dates(message):
        user_id = message.from_user.id
        events = fetch_upcoming_events_for_user(user_id)
        
        if not events:
            bot.send_message(
            message.chat.id,
            "У тебя нет предстоящих событий на ближайшие 2 недели. Возможно ты ещё не выбрал ни одной образовательной программы.\n\nПерейди в раздел: <b>Выбрать магистратуру</b> и я помогу определиться с выбором🤗",
            parse_mode="HTML")

        else:
            message_text = "📅 *Ваши предстоящие события на 2 недели:*\n\n"
            
            for event in events:
                try:
                    event_name = event['event_name']
                    program_name = event['program_name'].strip().capitalize()
                    event_date = event['event_date'].strftime('%d.%m.%Y')
                    description = event['description']
    
                    message_text += (
                        f"*{event_name}*\n"
                        f"Программа: *{program_name}*\n"
                        f"Дата: {event_date}\n"
                        f"Описание: {description}\n\n"
                    )
                    
                except Exception as e:
                    print(f"⛔ Ошибка при обработке события: {e}")
            
            bot.send_message(message.chat.id, message_text, parse_mode='Markdown')
        show_main_menu(message.chat.id)
    
    def fetch_upcoming_events_for_user(user_id):
        conn = connect_db_0()
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT 
                        pe.program_name, 
                        pe.event_name, 
                        pe.event_date, 
                        pe.description
                    FROM program_events pe
                    JOIN user_program_interest upi ON pe.program_name = upi.program_name
                    WHERE 
                        upi.user_id = %s
                        AND DATE(pe.event_date) BETWEEN CURDATE() AND CURDATE() + INTERVAL 14 DAY
                        AND (
                            upi.liked = 1
                            OR upi.program_name IN (
                                SELECT program_name FROM (
                                    SELECT program_name
                                    FROM user_program_interest
                                    WHERE user_id = %s
                                    ORDER BY questions_count DESC
                                    LIMIT 3
                                ) AS top_programs
                            )
                        )
                    ORDER BY pe.event_date ASC
                    LIMIT 10;
                """
                cursor.execute(sql, (user_id, user_id))
                return cursor.fetchall()
        finally:
            conn.close()
