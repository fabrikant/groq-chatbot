from dotenv import load_dotenv
import groq
from telegram.ext import ContextTypes

load_dotenv()

# Create a ChatBot
chatbot = None

def get_chatbot():
    return chatbot

def set_chatbot(cb):
    global chatbot
    chatbot = cb


async def generate_response(message: str, context: ContextTypes.DEFAULT_TYPE):
    """Generate a response to a message"""
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "user",
            "content": message,
        }
    ]
    response_queue = ""
    try:
        async for resp in await chatbot.chat.completions.create(
            messages=context.user_data.get("messages"),
            model=context.user_data.get("model", "llama3-8b-8192"),
            stream=True,
        ):
            if resp.choices[0].delta.content:
                response_queue += resp.choices[0].delta.content
            if len(response_queue) > 100:
                yield response_queue
                response_queue = ""
    except groq.GroqError as e:
        yield f"Error: {e}\nStart a new conversation, click /new"
    yield response_queue
