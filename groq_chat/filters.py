import os
from telegram import Update
from telegram.ext.filters import (
    UpdateFilter,
    COMMAND,
    TEXT,
    PHOTO,
    VOICE,
    AUDIO,
    Document,
    MessageFilter,
)
from dotenv import load_dotenv


load_dotenv()

_AUTHORIZED_USERS = [
    i.strip() for i in os.getenv("AUTHORIZED_USERS", "").split(",") if i.strip()
]


class AuthorizedUserFilter(UpdateFilter):
    def filter(self, update: Update):
        if not _AUTHORIZED_USERS:
            return True
        return (
            update.message.from_user.username in _AUTHORIZED_USERS
            or str(update.message.from_user.id) in _AUTHORIZED_USERS
        )


class StartsWithFilter(MessageFilter):
    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix

    def filter(self, message):
        # Важно: message.text может быть None (например, в чисто аудио-сообщениях)
        return bool(message.text and message.text.startswith(self.prefix))


AuthFilter = AuthorizedUserFilter()
MessageFilter = AuthFilter & ~COMMAND & TEXT
PhotoFilter = AuthFilter & ~COMMAND & (PHOTO | Document.IMAGE)
AudioFilter = AuthFilter & ~COMMAND & (VOICE | AUDIO | Document.AUDIO)
VoiceFilter = AuthFilter & COMMAND & StartsWithFilter("/set_voice_")
