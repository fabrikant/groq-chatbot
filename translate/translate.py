from googletrans import Translator
import os
import json
from db.async_database import get_user_setting, set_user_setting

LANG = os.getenv("LANG", "en")

translator = Translator()
with open("./translate/messages.json", "r", encoding="utf-8") as f:
    messages = json.load(f)


async def translate(text, context):
    lang = context.user_data.get("LANG", None)
    if not lang:
        chat_id = context._chat_id
        lang = await get_user_setting(chat_id, "lang", None)
        if not lang:
            await set_user_setting(chat_id, "lang", LANG)
            lang = LANG
        context.user_data["LANG"] = lang

    if lang == "en":
        return text

    try:
        static_text = messages[text].get(lang, None)
        if static_text:
            return static_text
    except KeyError:
        pass

    try:
        translation = await translator.translate(text, dest=lang)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")

    return text
