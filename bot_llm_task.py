# Ответы на вопросы
from telebot import types
import mysql.connector
import re
import random
from sentence_transformers import SentenceTransformer
from collections import defaultdict
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from dotenv import load_dotenv
import os

load_dotenv("config.env") # Загружаем переменные окружения из файла

from RAG  import rag_answer, DialogueContext
from db import connect_db
from programs_file import programs_list, emotion_stickers, salary_stickers

dialogue_contexts = {}
QDRANT_URL = os.getenv("QDRANT_URL")      
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def llm_tasks(bot, show_main_menu):

    def strip_non_letters(text):
        """
        Очищает текст от нежелательных символов, оставляя только
        русские буквы, пробелы, запятые, двоеточия и дефисы.
        Особо обрабатывает слова 'devops' и 'it', чтобы они не были удалены.
        """
        text = text.lower()
        if "devops" in text:
            return "devops-инженер облачных сервисов"
        elif "руководитель" in text:
            return "руководитель it-разработки"
        text = re.sub(r"[^а-яё ,:-]", "", text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip()
        return text
        
    user_state = {}
    
    @bot.message_handler(func=lambda message: message.text == "Вернуться в главное меню")
    def back_to_main_menu(message):
        chat_id = message.chat.id
        if chat_id in user_state:
            del user_state[chat_id]
        show_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "Задать вопрос 💙")
    def type_ask(message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn1 = types.KeyboardButton("Вопрос об образовательной программе")
        btn2 = types.KeyboardButton("Вопрос о чем-то другом")
        btn3 = types.KeyboardButton("Вернуться в главное меню")
        markup.add(btn1, btn2, btn3)
        bot.send_message(message.chat.id, "Выбери, о чем бы ты хотел узнать", reply_markup=markup)
    @bot.message_handler(func=lambda message: message.text == "Узнать о программе подробнее" or message.text == "Вопрос об образовательной программе"
                        or message.text == "Задать вопрос об образовательной программе 💙")
    def ask_program_name(message):
        bot.send_message(
            message.chat.id,
            "Введи максимально точное название образовательной программы на русском языке"
        )
        user_state[message.chat.id] = {'step': 'waiting_for_program_name'}
    @bot.message_handler(func=lambda message: message.text == "Задать вопрос о другой программе")
    def ask_repeat_program_selection(message):
        user_id = message.chat.id
        if user_id not in user_state:
            user_state[user_id] = {}
        user_state[user_id]['step'] = 'waiting_for_program_name'
        user_state[user_id]['program_name'] = 'itmoshka_bot'
        ask_program_name(message)
    @bot.message_handler(func=lambda message: message.text == "Вопрос о чем-то другом" or message.text == "Спросить не об образовательной программе")
    def ask_no_program(message):
        program_name = ''
        user_id = message.chat.id
        user_state[user_id] = {
            'step': 'waiting_for_question',
            'program_name': 'itmoshka_bot',
            'message_count': 0 
        }
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Задать вопрос об образовательной программе 💙"))
        markup.add(types.KeyboardButton("Вернуться в главное меню"))
        bot.send_message(
        user_id,
        "Отлично! Я готов рассказать тебе всё о поступлении в ИТМО.\nЕсли хочешь узнать о конкретной программе, пожалуйста, нажми\n\n<b>Задать вопрос об образовательной программе 💙</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )
    @bot.message_handler(func=lambda message: message.text == "Хочу поступить на эту программу 💜")
    def handle_like_program(message):
        user_id = message.chat.id
        program_name = user_state.get(user_id, {}).get("program_name")
    
        if program_name:
            like_program(user_id, program_name)  # записываем интерес в БД
            clean_program_name = " ".join(program_name.lower().split()).capitalize()
            msg = (
                f"Отлично! Я напомню тебе о важных датах для образовательной программы <b>{clean_program_name}</b>\n"
                f"А пока я готов ответить на твои вопросы 🤗"
            )
            bot.send_message(user_id, msg, parse_mode="HTML")
        else:
            bot.send_message(user_id, "Сначала выбери программу")
            
        
    @bot.message_handler(func=lambda message: user_state.get(message.chat.id, {}).get('step') == 'waiting_for_program_name' and user_state.get(message.chat.id, {}).get('program_name') != '')
    def handle_program_name(message):
        program_name = strip_non_letters(message.text.strip())
        user_id = message.chat.id
         # Проверяем, есть ли введенная программа в списке
        if program_name not in programs_list:
            bot.send_sticker(user_id, "CAACAgIAAxkBAAIGbmg0TyV0K-v_uOpXJs1hhzviKRMYAAJAhQACB3ChSUp1xCrLZLXbNgQ")
            bot.send_message(user_id, "Извини, я не нашел такой программы \nпопробуй ввести название снова")
            user_state[message.chat.id] = {'step': 'waiting_for_program_name'}
            return
        user_id = message.chat.id
        if user_id not in user_state:
            user_state[user_id] = {}
        user_state[user_id] = {
            'step': 'waiting_for_question',
            'program_name': program_name,
            'message_count': 0 
        }
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Хочу поступить на эту программу 💜")
        markup.add("Задать вопрос о другой программе", "Вернуться в главное меню")
        markup.add("Спросить не об образовательной программе")

        bot.send_message(user_id, "Отлично! Я готов рассказать о программе. Что тебя интересует?", reply_markup=markup)

    def like_program(user_id, program_name): #Записывает в БД интерес пользователя к образовательной программе
        conn = connect_db()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO user_program_interest (user_id, program_name, questions_count, liked, updated_at)
                    VALUES (%s, %s, 0, TRUE, NOW())
                    ON DUPLICATE KEY UPDATE
                        liked = TRUE,
                        updated_at = NOW()
                """, (user_id, program_name.lower()))
            conn.commit()

    def convert_bold_markdown_to_html(text: str) -> str:
        return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    def format_list_markers(text: str) -> str:
        text = re.sub(r"(?m)^\*\s+", "• ", text)
        return text
    def prepare_html_answer(text: str) -> str:
        html = convert_bold_markdown_to_html(text)
        html = format_list_markers(html)
        return html

    @bot.message_handler(func=lambda message: user_state.get(message.chat.id, {}).get('step') == 'waiting_for_question')
    def handle_question_for_program(message):
        user_id = message.chat.id
        state = user_state.get(user_id)
        if not state or 'program_name' not in state:
            bot.send_message(user_id, "Сначала выбери образовательную программу.")
            return
        question = message.text
        program_name = user_state[user_id]['program_name'].lower()
    
        # Инициализация диалогового контекста
        dialogue_context = dialogue_contexts.setdefault(user_id, DialogueContext())
    
        save_user_question(user_id, program_name, question)
        thinking_msg = bot.send_message(user_id, "⏳ Думаю над ответом...")
    
        try:
            answer = prepare_html_answer(rag_answer(question, program_name, dialogue_context=dialogue_context))
            bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
    
            if is_salary_question(question):
                sticker_id = random.choice(salary_stickers)
                bot.send_sticker(user_id, sticker_id)
            elif should_send_sticker(user_id):
                send_random_emotion_sticker(user_id)
                user_state[user_id]["message_count"] = 0
            bot.send_message(user_id, answer, parse_mode="HTML")
    
        except Exception as e:
            bot.delete_message(chat_id=user_id, message_id=thinking_msg.message_id)
            bot.send_message(user_id, f"Произошла ошибка при получении ответа: {str(e)}")

    def save_user_question(user_id, program_name, question):
        conn = connect_db()
        with conn:
            with conn.cursor() as cursor:
                # Добавляем в users_questions
                cursor.execute("""
                    INSERT INTO users_questions (user_id, program_name, question)
                    VALUES (%s, %s, %s)
                """, (user_id, program_name, question))
                 #запоминанаем интерес к программе
                cursor.execute("""
                    INSERT INTO user_program_interest (user_id, program_name, questions_count, liked, updated_at)
                    VALUES (%s, %s, 1, FALSE, NOW())
                    ON DUPLICATE KEY UPDATE
                        questions_count = questions_count + 1,
                        updated_at = NOW()
                """, (user_id, program_name))
            conn.commit()
            
    def is_salary_question(question: str) -> bool:
        keywords = ["зарплат", "оплат", "доход", "заработ", "сколько платят", "сколько получают"]
        return any(kw in question.lower() for kw in keywords)
    def should_send_sticker(user_id):
        state = user_state.setdefault(user_id, {})
        count = state.get("message_count", 0) + 1
        state["message_count"] = count
        return count >= random.choice([4, 5, 6])
    def send_random_emotion_sticker(chat_id):
        sticker_id = random.choice(emotion_stickers)
        bot.send_sticker(chat_id, sticker_id)