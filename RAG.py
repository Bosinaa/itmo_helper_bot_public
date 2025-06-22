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
def get_model_response(messages, api_key: str, model_name: str = MODEL_ID, max_tokens: int = 400):
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
def rag_answer(question, program_name, dialogue_context: DialogueContext, top_k: int = 7):
    # Последние 3 сообщения из истории
    history = dialogue_context.history[-6:]
    recent_history = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    
    # Эмбеддинг
    full_query = f"{recent_history}\nuser: {question}"
    query_vector = get_embedding(f"query: {full_query}")

    # Поиск
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

    # Разделяем результаты по источнику
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
    
    # Ограничиваем itmoshka_bot до 2 чанков, если указан program_name
    if program_name != "itmoshka_bot":
        itmoshka_chunks = itmoshka_chunks[:2]
    
    # Объединяем контекст
    context_chunks = program_chunks + itmoshka_chunks
    context = "\n---\n".join(context_chunks)

    # Контекст
    #context_chunks = [hit.payload.get("текст") or hit.payload.get("text") for hit in results if hit.payload]
    #context = "\n---\n".join(context_chunks)

    # Промпт
    prompt = f"""
Ты — ассистент для поступающих в магистратуру ИТМО. Отвечай на вопрос без вступления. Здороваться запрещено.
{'Вот выдержки с сайта магистратуры ИТМО' + (f' «{program_name}»:' if program_name else ':')}
{context}

Сначала постарайся ответить на вопрос, опираясь на приведённый контекст.  
Если данных в контексте недостаточно — дополни ответ проверенной и актуальной информацией. Не говори, откуда берешь информацию.
Отвечай четко на поставленный вопрос — избегай абстрактных или расплывчатых фраз.  
Твой стиль — дружелюбный собеседник: 50% доброжелательности, 50% экспертности. Говори грамотно, можешь шутить и выражать эмоции.
Если человек выражает сомнение, тревогу или усталость — мягко поддержи.  
Дай понять, что его чувства нормальны, и предложи следующий шаг. Например:  
«Такое ощущение — это нормально, особенно когда много вариантов. Хочешь, разберём вместе, что тебе действительно важно?»
Если вопрос связан с выбором вуза или сравнениями — подчёркивай сильные стороны ИТМО
В конце некоторых ответов (не чаще чем в 1 из 5 ответов) можешь задавать вопросы для продолжения диалога.

Если вопрос не относится к обучению, поступлению, карьере или ИТМО — мягко объясни, что фокусируешься именно на этих темах.

Вопрос: {question}
Ответ:
""".strip()

    messages = dialogue_context.get_chat_messages(prompt)
    response = get_model_response(messages=messages, api_key=api_key)

    # Обновляем историю
    dialogue_context.add_message("user", question)
    dialogue_context.add_message("assistant", response)

    # Хинт
    additional_hint = ""
    if not program_name and any(kw in question.lower() for kw in ["програм", "магистратур", "учит", "направлен"]):
        additional_hint = '\n\nЕсли ты хочешь узнать подробности о конкретной программе, нажми "Задать вопрос о программе"'

    return response + additional_hint

    
