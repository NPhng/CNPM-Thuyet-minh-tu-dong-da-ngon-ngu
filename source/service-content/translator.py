"""Module dịch ngôn ngữ cho Content Service."""

LANG_MAP = {
    "en": "en",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
}


def translate_text(text: str, lang: str) -> str:
    if not text or not text.strip():
        return ""
    from deep_translator import GoogleTranslator

    target_code = LANG_MAP.get(lang, lang)
    translated = GoogleTranslator(source="vi", target=target_code).translate(text)
    return translated or ""
