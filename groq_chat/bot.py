import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PicklePersistence,
)
from groq_chat.llm_conversation import llm_request
from groq_chat.control_panel import control_panel_builder, control_panel_executor
from groq_chat.model_changer import change_model_callback_handler
from groq_chat.handlers import (
    start,
    help_command,
    new_command_handler,
    SYSTEM_PROMPT_SP,
    CANCEL_SP,
    start_system_prompt,
    get_system_prompt,
    cancelled_system_prompt,
    error_handler,
)
from groq_chat.groq_chat import set_chatbot
from groq import AsyncGroq
import httpx
from groq_chat.filters import AuthFilter, MessageFilter
from dotenv import load_dotenv
import logging
from telegram import Update, BotCommand
from translate.translate import translate
import groq_chat.command_descriptions as com_descr

from db.async_database import initialize_db

load_dotenv()

logger = logging.getLogger(__name__)


async def set_bot_commands(app):

    commands = [
        BotCommand("start", await translate(com_descr.start)),
        BotCommand("panel", await translate(com_descr.panel)),
        # BotCommand("model", await translate(com_descr.model)),
        # BotCommand("new", await translate(com_descr.new)),
        # BotCommand("info", await translate(com_descr.info)),
        # BotCommand("help", await translate(com_descr.help)),
        # BotCommand("system_prompt", await translate(com_descr.system_prompt)),
    ]
    # `app.bot` уже инициализирован к моменту вызова `run_polling()`
    await app.bot.set_my_commands(commands)
    logger.info("Команды бота установлены в Telegram UI")


async def init_chatbot(app):
    set_chatbot(
        AsyncGroq(api_key=os.getenv("GROQ_API_KEY"), http_client=httpx.AsyncClient())
    )


async def prepare_bot(app):
    await initialize_db()
    await set_bot_commands(app)
    await init_chatbot(app)


def start_bot():
    logger.info("Starting bot")

    app_builder = Application.builder().token(os.getenv("BOT_TOKEN"))

    persistence = PicklePersistence(filepath="./data/telegram-bot-data")
    app_builder.persistence(persistence)

    # Build the app
    app = app_builder.build()

    app.add_handler(CommandHandler("start", start, filters=AuthFilter))
    app.add_handler(CommandHandler("panel", control_panel_builder, filters=AuthFilter))
    # app.add_handler(CommandHandler("model", model_command_handler, filters=AuthFilter))
    # app.add_handler(CommandHandler("info", info_command_handler, filters=AuthFilter))
    app.add_handler(CommandHandler("new", new_command_handler, filters=AuthFilter))
    app.add_handler(CommandHandler("help", help_command, filters=AuthFilter))

    app.add_handler(
        ConversationHandler(
            entry_points=[
                CommandHandler("system_prompt", start_system_prompt, filters=AuthFilter)
            ],
            states={
                SYSTEM_PROMPT_SP: [MessageHandler(MessageFilter, get_system_prompt)],
                CANCEL_SP: [
                    CommandHandler(
                        "cancel", cancelled_system_prompt, filters=AuthFilter
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancelled_system_prompt, filters=AuthFilter)
            ],
        )
    )

    app.add_handler(MessageHandler(MessageFilter, llm_request))
    app.add_handler(
        CallbackQueryHandler(change_model_callback_handler, pattern="^change_model_")
    )

    app.add_handler(
        CallbackQueryHandler(control_panel_executor, pattern="^ctrl_panel_")
    )

    app.add_error_handler(error_handler)
    if app.post_init:
        app.post_init.append(prepare_bot)
    else:
        app.post_init = prepare_bot

    # Run the bot until the user presses Ctrl-C
    app.run_polling(allowed_updates=Update.ALL_TYPES)
