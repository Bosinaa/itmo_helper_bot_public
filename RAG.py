from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MinShould, MatchAny
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
import requests
from dotenv import load_dotenv
import os

load_dotenv("config.env")  # Загружает переменные из config.env

api_key = os.getenv("GEMINI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")      
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "abit-itmo-rag"
MODEL_ID = "google/gemini-2.5-flash-preview"
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")

# Новый DialogueContext с chat-style историей
class DialogueContext:
    def __init__(self, max_history: int = 3):
        self.history = []
        self.max_history = max_history
    
    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2:]

    def get_formatted_history(self) -> str:
        return "\n".join([f"{m['role']}: {m['content']}" for m in self.history])

    def get_chat_messages(self, prompt: str):
        return self.history + [{"role": "user", "content": prompt}]

#Преобразуем запрос в эмбеддинг
def get_embedding(text: str):
    return embedding_model.encode(text, normalize_embeddings=True).tolist()


# Модифицированный get_model_response — принимает messages
def get_model_response(messages, api_key: str, model_name: str = MODEL_ID, max_tokens: int = 1000):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Error {response.status_code}: {response.text}")


# Главная функция RAG с диалогом
def rag_answer(question, program_name, dialogue_context: DialogueContext, top_k: int = 15):
    # Последние 3 сообщения из истории
    history = dialogue_context.history[-4:]
    recent_history = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    
    # Создание эмбеддингов
    query_vector = get_embedding(question, is_query=True)

    # Поиск но Qdrant
    search_filter = (
        Filter(must=[FieldCondition(
            key="program",
            match=MatchAny(any=[program_name.lower(), "itmoshka_bot"]))])
        if program_name else None
    )

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        query_filter=search_filter
    )

    # разделение дезультатов в зависимости от источника
    program_chunks = []
    itmoshka_chunks = []
    
    for hit in results:
        if not hit.payload:
            continue
        source = hit.payload.get("program", "").lower()
        chunk_text = hit.payload.get("текст") or hit.payload.get("text") or ""
        if source == "itmoshka_bot":
            itmoshka_chunks.append(chunk_text)
        else:
            program_chunks.append(chunk_text)
    
    # Ограничение itmoshka_bot до 2 чанков, если вопрос о конкретной программе (указан program_name)
    if program_name != "itmoshka_bot":
        itmoshka_chunks = itmoshka_chunks[:2]
    
    # Формирование общего контекста
    context_chunks = program_chunks + itmoshka_chunks
    context = "\n---\n".join(context_chunks)
    # Промпт
    prompt = f"""
    Ты — Итмошка, AI-ассистент для поступающих в магистратуру ИТМО. Ты помогаешь абитуриентам разобраться в поступлении, выборе программы, обучении, карьерных перспективах. Твоя задача, поддержать, помочь и замотивировать выбрать ИТМО.
    Отвечай **по сути**, **без вступлений** и **без повторов**. Если нужно — используй списки, примеры или короткие фразы. Пиши **человечно**, как живой и умный собеседник.
    {'Вот выдержки с сайта магистратуры ИТМО' + (f' «{program_name}»:' if program_name != "itmoshka_bot" else ':')}
    {context}
    Отвечай, опираясь на приведённый контекст. Будь внимателен к названиям программ, срокам, цифрам. Если в выдержках указаны цифры обязательно процитируй их дословно, эти данные важны — не игнорируй их. Ничего не придумывай. Если информации в контексте нет — можешь кратко дополнить ответ достоверной информацией, не ссылаясь на источник.
    
    **Если вопрос про разницу между ИТМО и другими вузами** — мягко подчёркивай сильные стороны ИТМО без критики других:
    • проектное обучение 
    • исследовательские лаборатории  
    • высокие позиции в российских и международных рейтингах
    • преподаватели - практикующие специалисты 
    • гибкие образовательные треки и индивидуальный план  
    • стажировки, хакатоны, международные возможности  
    • карьерное развитие уже во время учёбы 
    
    Если человек с опытом — не объясняй очевидное. Делай акцент на проектность, структуру, гибкость, индустриальный фокус.
    
    Твой стиль — 60% доброжелательности, 50% экспертности. Можно немного юмора.
    Если человек устал или сомневается — поддержи. Дай понять, что это нормально, и предложи следующий шаг.
    Если тема не относится к поступлению, обучению, ИТМО или карьере — объясни вежливо, что ты фокусируешься на этих темах.
    В конце (если уместно) — предложи продолжение диалога, задай наводящий вопрос.
    
    Вопрос: {question}   
    Ответ:
    """.strip()

    messages = [{"role": "system", "content": prompt}] + dialogue_context.history + [{"role": "user", "content": question}]
    response = get_model_response(messages=messages, api_key=api_key)

    # Обновление истории
    dialogue_context.add_message("user", question)
    dialogue_context.add_message("assistant", response)

    # Напоминание о возможности переключиться в режим "узнать об образовательное программе"
    additional_hint = ""
    if program_name == "itmoshka_bot" and any(kw in question.lower() for kw in ["програм", "магистратур", "учит", "направлен"]):
        additional_hint = '\n\nЕсли ты хочешь узнать подробности о конкретной программе, нажми: \n**Задать вопрос о программе 💙**'
    return response + additional_hint