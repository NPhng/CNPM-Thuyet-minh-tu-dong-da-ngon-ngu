from __future__ import annotations

import json
import logging
import os
import re
import threading
import time

import httpx

logger = logging.getLogger("translator")

TARGET_LANGS = ("en", "zh", "ja", "ko")
_MYMEMORY_CODES = {"en": "en", "zh": "zh-CN", "ja": "ja", "ko": "ko"}
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_MAX_CHUNK = 450
_MIN_INTERVAL = 0.4
_CACHE_MAX = 500

_lock = threading.Lock()
_last_call = 0.0
_text_cache: dict[tuple[str, str], str] = {}


def _put_cache(cache: dict, key, value, limit: int) -> None:
    if len(cache) >= limit:
        cache.pop(next(iter(cache)))
    cache[key] = value

def _gemini_translate(name: str, description: str) -> dict:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    prompt = (
        "Translate this zoo exhibit's Vietnamese name and description into English (en), "
        "Simplified Chinese (zh), Japanese (ja) and Korean (ko). Keep proper nouns and "
        "scientific names where appropriate, use a natural friendly tone for visitors, and do "
        "not add or remove information. Reply with JSON only, exactly this shape: "
        '{"en":{"name":"","description":""},"zh":{"name":"","description":""},'
        '"ja":{"name":"","description":""},"ko":{"name":"","description":""}}\n\n'
        "Input: " + json.dumps({"name": name, "description": description}, ensure_ascii=False)
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 4096,
            "temperature": 0.2,
        },
    }
    resp = httpx.post(
        _GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": key},
        json=body,
        timeout=20.0,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    data = json.loads(text)
    result: dict = {}
    for lang in TARGET_LANGS:
        item = data.get(lang) or {}
        n, d = item.get("name"), item.get("description")
        if not (isinstance(n, str) and n.strip() and isinstance(d, str) and d.strip()):
            raise ValueError(f"Gemini trả thiếu dữ liệu cho {lang}")
        result[lang] = {"name": n.strip(), "description": d.strip()}
    return result

def _split_text(text: str, limit: int = _MAX_CHUNK) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    cur = ""
    for piece in re.split(r"(?<=[.!?。！？\n])\s+", text):
        while len(piece) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(piece[:limit])
            piece = piece[limit:]
        if cur and len(cur) + 1 + len(piece) > limit:
            chunks.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip() if cur else piece
    if cur:
        chunks.append(cur)
    return chunks


def _mymemory_call(chunk: str, code: str) -> str:
    global _last_call
    params = {"q": chunk, "langpair": f"vi|{code}"}
    email = os.getenv("MYMEMORY_EMAIL", "").strip()
    if email:
        params["de"] = email
    with _lock:  # giãn cách giữa các lần gọi
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    resp = httpx.get(_MYMEMORY_URL, params=params, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if int(data.get("responseStatus", 0)) != 200:
        raise RuntimeError(f"MyMemory lỗi {data.get('responseStatus')}")
    out = (data.get("responseData") or {}).get("translatedText") or ""
    if not out.strip() or "MYMEMORY WARNING" in out.upper():
        raise RuntimeError("MyMemory không trả bản dịch (hết hạn mức?)")
    return out


def translate_text(text: str, lang: str) -> str:
    if lang not in _MYMEMORY_CODES:
        raise ValueError(f"Ngôn ngữ không hỗ trợ: {lang}")
    if not text or not text.strip():
        return ""
    key = (lang, text)
    if key in _text_cache:
        return _text_cache[key]
    code = _MYMEMORY_CODES[lang]
    result = " ".join(_mymemory_call(c, code) for c in _split_text(text))
    _put_cache(_text_cache, key, result, _CACHE_MAX)
    return result

def translate_poi(name: str, description: str) -> dict:
    """Trả {"en": {"name","description"}, "zh": {...}, "ja": {...}, "ko": {...}}."""
    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            return _gemini_translate(name, description)
        except Exception as exc:  # không log nội dung lỗi để khỏi lộ key/URL
            status = getattr(getattr(exc, "response", None), "status_code", "")
            logger.warning("Gemini dịch lỗi (%s %s), chuyển sang MyMemory", type(exc).__name__, status)
    return {
        lang: {
            "name": translate_text(name, lang),
            "description": translate_text(description, lang),
        }
        for lang in TARGET_LANGS
    }