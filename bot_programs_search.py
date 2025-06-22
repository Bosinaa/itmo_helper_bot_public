# Подбор образовательной программы
from telebot import types
import re
from sentence_transformers import SentenceTransformer
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
import pymorphy2
from db import connect_db

def program_tasks(bot, show_main_menu):
    # Загрузка модели эмбеддингов для семантического поиска
    model = SentenceTransformer('intfloat/multilingual-e5-base')
    # Подключение к векторной БД Qdrant
    QDRANT_URL = os.getenv("QDRANT_URL")      
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    # Состояние пользователя по chat_id
    user_state = {}
    # Инициализация морфоанализатора
    morph = pymorphy2.MorphAnalyzer()
    # Лемматизация
    def lemmatize_words(words: list[str]) -> set[str]:
        return set(morph.parse(word)[0].normal_form for word in words if word.isalpha())
    
    def search_educational_programs(
        query_text: str,
        top_k = 10,
        min_score = 0.5,
        keyword_boost: bool = True,
        filter_keywords = None,
        final_score_threshold = 0.7
    ) -> list[dict]:
        # Лемматизация запроса
        query_words = re.findall(r'\w+', query_text.lower())
        query_keywords = lemmatize_words(query_words)
    
        # Нормализуем фильтры
        normalized_filter_keywords = [kw.lower() for kw in filter_keywords] if filter_keywords else None
        query_embedding = model.encode(query_text).tolist()
    
        # Если указаны фильтры — добавим фильтрацию по ним
        query_filter = None
        if normalized_filter_keywords:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="metadata.keywords_lower",
                        match=MatchAny(any=normalized_filter_keywords)
                    )
                ]
            )
    
        results = client.search(
            collection_name="abit-itmo-programs",
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=top_k * 5,
            with_payload=True,
            score_threshold=min_score
        )
    
        # Boost по ключевым словам, названию, описанию
        if keyword_boost and results:
            boosted_results = []
            for hit in results:
                payload = hit.payload
                keywords = lemmatize_words(payload["metadata"].get("keywords", []))
                title = lemmatize_words(re.findall(r'\w+', payload["название"].lower()))
                description = lemmatize_words(re.findall(r'\w+', payload["описание"].lower()))
    
                # Подсчёт количества совпадений
                match_keywords = len(query_keywords & keywords)
                match_title = len(query_keywords & title)
                match_desc = len(query_keywords & description)
    
                # Вычисляем boost
                boost = 1.0
                boost += 0.25 * match_keywords
                boost += 0.5 * match_title
                boost += 0.1 * match_desc
    
                # Если ни одно поле не совпадает — штраф
                if match_keywords == 0 and match_title == 0:
                    boost *= 0.6
    
                hit.score *= boost
                boosted_results.append(hit)
    
            results = [
                hit for hit in boosted_results if hit.score >= final_score_threshold
            ]
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:top_k]
    
        return [
            {
                "title": hit.payload["название"],
                "match_score": round(hit.score, 3),
                "description": hit.payload["описание"],
                "link": hit.payload["metadata"]["ссылка"]
            }
            for hit in results[:3]
        ]
    
    def escape_markdown_v2(text):
        if not text:
            return ''
        escape_chars = r'\_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
    
    # === Хендлеры ===
    # Обработка выбора образовательной программы
    @bot.message_handler(func=lambda message: message.text == "Выбрать магистратуру")
    def ask_interest(message):
        bot.send_message(
            message.chat.id,
            "Расскажи, что бы ты хотел изучать — и я подберу подходящие программы"
        )
        user_state[message.chat.id] = 'waiting_for_interest'
    # Возвращение в главное меню
    @bot.message_handler(func=lambda message: message.text == "Вернуться в главное меню")
    def back_to_main_menu(message):
        chat_id = message.chat.id
        if chat_id in user_state:
            del user_state[chat_id]
        show_main_menu(chat_id)
    # Повторный выбор образовательной программы
    @bot.message_handler(func=lambda message: message.text == "Выбрать программу снова")
    def repeat_program_selection(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "Расскажи, какую магистратуру ты ищешь")
        user_state[chat_id] = 'waiting_for_interest'
    # Отправка до 3 образовательных программ
    @bot.message_handler(func=lambda message: user_state.get(message.chat.id) == 'waiting_for_interest' or (
        isinstance(user_state.get(message.chat.id), dict) and user_state.get(message.chat.id, {}).get('step') == 'waiting_for_interest'))
    def handle_interest(message):
        query = message.text
        matches = search_educational_programs(query)
    
        if matches:
            response = "Вот подходящие программы:\n\n"
            for prog in matches:
                title = escape_markdown_v2(prog.get('title', 'Без названия'))
                description = escape_markdown_v2(prog.get('description', ''))
                link = escape_markdown_v2(prog.get('link', ''))
                response += f"🎓 *{title}*\n{description}\n{link}\n"
    
            bot.send_message(
                message.chat.id,
                response.strip(),
                parse_mode='MarkdownV2'
            )
            user_state[message.chat.id] = {
                'last_matches': matches,
                'step': 'after_search'
            }
    
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add("Узнать о программе подробнее")
            markup.add("Выбрать программу снова", "Вернуться в главное меню")
    
            bot.send_message(
            message.chat.id,
            "Хочешь узнать подробнее об одной из этих программ?\nНажми <b>Узнать о программе подробнее</b>",
            reply_markup=markup, parse_mode="HTML")
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add("Выбрать программу снова", "Вернуться в главное меню")
            bot.send_message(
                message.chat.id,
                "Не удалось найти подходящие программы. Попробуй переформулировать запрос или посети наш сайт: https://abit.itmo.ru/master",
                reply_markup=markup
            )
            bot.send_sticker(message.chat.id, "CAACAgIAAxkBAAIGdWg0T-k_wg6GxgTNmd6qm9LDkyPMAALidwACREyZSaa6TlUTzrRcNgQ")
