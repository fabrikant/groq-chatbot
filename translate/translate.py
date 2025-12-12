from googletrans import Translator
import os
import json

LANG = os.getenv("LANG", "en")

translator = Translator()
with open('./translate/messages.json', 'r', encoding='utf-8') as f:
    messages = json.load(f)

async def translate(text):
    try:
        static_text = messages[text].get(LANG, None)
        if static_text:
            return static_text
    except KeyError:
        pass

    try:
        translation = await translator.translate(text, dest=LANG)
        return translation.text
    except Exception as e:
        print(f"Translation error: {e}")        

    return text

