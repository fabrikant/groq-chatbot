from groq_chat.bot import start_bot
import logging
import os

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    log_level = os.getenv("LOG_LEVEL", default="info")

    logger_level = logging.INFO
    if log_level.lower().strip() in ["critical", "error"]:
        logger_level = logging.ERROR
    elif log_level.lower().strip() == "warning":
        logger_level = logging.WARNING
    elif log_level.lower().strip() == "info":
        logger_level = logging.INFO
    elif log_level.lower().strip() in ["debug", "trace"]:
        logger_level = logging.DEBUG

    logging.basicConfig(
        level=logger_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    start_bot()
