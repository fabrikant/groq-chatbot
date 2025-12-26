import os
from dotenv import load_dotenv
import groq
from telegram.ext import ContextTypes
from translate.translate import translate
from io import BytesIO
from db.async_database import get_user_setting

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
        if available_models:
            available_models.sort()
    return available_models


async def get_default_model() -> str:
    """Get the default model to use"""
    global available_models
    if not available_models:
        await get_groq_models()
    default_model_name = os.getenv("DEFAULT_GROQ_MODEL", "llama-3.3-70b-versatile")
    if available_models:
        if default_model_name in available_models:
            return default_model_name
        elif len(available_models) > 0:
            return available_models[0]
        else:
            return default_model_name
    else:
        return default_model_name


async def groq_chat_completion_create(
    context: ContextTypes.DEFAULT_TYPE, model: str
) -> str:

    full_request_content = []
    prompt_str = context.user_data.get("system_prompt", None)
    if prompt_str:
        full_request_content += [{"role": "system", "content": prompt_str}]

    full_request_content += context.user_data["messages"]
    full_response_content = ""

    try:
        completion = await chatbot.chat.completions.create(
            messages=full_request_content,
            model=model,
            stream=False,
        )

        if completion.choices:
            full_response_content = completion.choices[0].message.content

        return full_response_content

    except groq.GroqError as e:

        message = e.body.get("error", {}).get("message")
        status_code = e.status_code
        if status_code == 413:
            message += await translate(
                "\nTry resetting the context. Use the command /new", context
            )

        return f"{await translate("Groq API returned an error", context)}: {status_code} ({message})"


async def generate_ocr_response(
    base64_image: str, message: str, context: ContextTypes.DEFAULT_TYPE
) -> str:

    model = await get_user_setting(
        context._user_id,
        "ocr_model",
        context.user_data.get("model", await get_default_model()),
    )
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": message},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                    },
                },
            ],
        }
    ]

    return await groq_chat_completion_create(context, model=model)


async def generate_stt_response(
    audio_bytes: BytesIO, message: str, context: ContextTypes.DEFAULT_TYPE
) -> str:
    try:
        model = await get_user_setting(
            context._user_id,
            "stt_model",
            context.user_data.get("model", await get_default_model()),
        )
        transcription = await chatbot.audio.transcriptions.create(
            file=audio_bytes,
            model=model,
            prompt=message,
            response_format="text",
        )
        return transcription
    except groq.GroqError as e:

        message = e.body.get("error", {}).get("message")
        status_code = e.status_code
        if status_code == 413:
            message += await translate(
                "\nTry resetting the context. Use the command /new", context
            )

        return f"{await translate("Groq API returned an error", context)}: {status_code} ({message})"
    except Exception as e:
        return str(e)


async def generate_tts_response(
    message: str, context: ContextTypes.DEFAULT_TYPE
) -> str:
    model = await get_user_setting(
        context._user_id,
        "tts_model",
        context.user_data.get("model", await get_default_model()),
    )
    try:
        response = await chatbot.audio.speech.create(
            model=model,
            voice="autumn",
            response_format="wav",
            input=message,
        )
        # await response.stream_to_file("./data/response.wav")
        return response

    except groq.GroqError as e:
        message = e.body.get("error", {}).get("message")
        status_code = e.status_code
        return f"{await translate("Groq API returned an error", context)}: {status_code} ({message})"
    except Exception as e:
        return str(e)


async def generate_response(message: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["messages"] = context.user_data.get("messages", []) + [
        {
            "role": "user",
            "content": message,
        }
    ]
    model = context.user_data.get("model", await get_default_model())
    return await groq_chat_completion_create(context, model=model)
