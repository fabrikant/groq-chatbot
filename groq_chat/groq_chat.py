from dotenv import load_dotenv
import groq
from telegram.ext import ContextTypes


load_dotenv()

# Create a ChatBot
chatbot = None
available_models = None


def get_chatbot():
    return chatbot


def set_chatbot(cb):
    global chatbot
    chatbot = cb


async def get_groq_models() -> dict:
    global available_models
    if chatbot:
        models = await chatbot.models.list()
        available_models = [model.id for model in models.data]
    return available_models


async def get_default_model() -> str:
    """Get the default model to use"""
    global available_models
    if not available_models:
        await get_groq_models()

    if available_models:
        if "llama3-8b-8192" in available_models:
            return "llama3-8b-8192"
        elif len(available_models) > 0:
            return available_models[0]
        else:
            return "llama3-8b-8192"  # Fallback default model
    else:
        return "llama3-8b-8192"  # Fallback default model


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
            model=context.user_data.get("model", await get_default_model()),
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
