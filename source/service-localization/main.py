from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import hashlib
import time

# Thư viện dịch thuật
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    print("⚠️ deep-translator chưa được cài. Dịch sẽ dùng mock data.")

CONTENT_SERVICE_URL = "http://content-service:8002"

# Supported languages
SUPPORTED_LANGUAGES = {
    "vi": "Tiếng Việt",
    "en": "English",
    "zh": "中文 (Chinese)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)"
}

# Mapping mã ngôn ngữ của app → mã của Google Translate
GOOGLE_LANG_MAP = {
    "vi": "vi",
    "en": "en",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko"
}

translation_cache = {}

app = FastAPI(
    title="Zoo Localization Service",
    description="Service dịch đa ngôn ngữ - 3-Tier Fallback cho Thảo Cầm Viên",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hàm dịch thuật cốt lõi

def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang == target_lang:
        return text  # Không cần dịch nếu cùng ngôn ngữ
    
    if not TRANSLATOR_AVAILABLE:
        # Mock translation khi chưa cài thư viện
        return f"[{target_lang.upper()}] {text}"
    
    try:
        google_target = GOOGLE_LANG_MAP.get(target_lang, target_lang)
        google_source = GOOGLE_LANG_MAP.get(source_lang, source_lang)
        
        translator = GoogleTranslator(source=google_source, target=google_target)
        translated = translator.translate(text)
        return translated
    except Exception as e:
        print(f"Lỗi dịch thuật: {e}")
        return text  # Trả về text gốc nếu dịch lỗi


def get_cache_key(poi_id: str, lang: str) -> str:
    return f"{poi_id}_{lang}"


def get_cached_translation(poi_id: str, lang: str) -> Optional[dict]:
    key = get_cache_key(poi_id, lang)
    cached = translation_cache.get(key)
    if cached:
        # Kiểm tra còn hạn không
        if time.time() - cached["cached_at"] < 3600:
            return cached
    return None


def save_to_cache(poi_id: str, lang: str, data: dict):
    key = get_cache_key(poi_id, lang)
    translation_cache[key] = {
        **data,
        "cached_at": time.time()
    }


async def get_poi_content(poi_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{CONTENT_SERVICE_URL}/pois/{poi_id}",
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy POI '{poi_id}'")
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Content Service không phản hồi")

# 3-Tier Fallback Logic

def apply_3tier_fallback(poi: dict, lang: str) -> dict:
    # Tier 1: Thử ngôn ngữ yêu cầu
    lang_key = f"description_{lang}"
    if poi.get(lang_key):
        return {
            "text": poi[lang_key],
            "tier": 1,
            "actual_lang": lang,
            "is_fallback": False,
            "fallback_reason": None
        }
    
    # Tier 2: English Fallback
    if lang != "en" and poi.get("description_en"):
        return {
            "text": poi["description_en"],
            "tier": 2,
            "actual_lang": "en",
            "is_fallback": True,
            "fallback_reason": f"Chưa có bản dịch '{lang}', dùng tiếng Anh"
        }
    
    # Tier 3: Vietnamese (bản gốc)
    return {
        "text": poi.get("description_vi", "Chưa có nội dung"),
        "tier": 3,
        "actual_lang": "vi",
        "is_fallback": True,
        "fallback_reason": f"Chưa có bản dịch '{lang}' và tiếng Anh, dùng tiếng Việt gốc"
    }

# API Endpoints
@app.get("/")
def root():
    return {
        "service": "Localization Service",
        "status": "đang chạy ✅",
        "supported_languages": SUPPORTED_LANGUAGES,
        "translator_available": TRANSLATOR_AVAILABLE
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "localization"}


@app.get("/languages")
def get_supported_languages():
    return {
        "total": len(SUPPORTED_LANGUAGES),
        "languages": SUPPORTED_LANGUAGES
    }


@app.get("/poi/{poi_id}")
async def get_poi_localization(poi_id: str, lang: str = "vi"):
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Ngôn ngữ '{lang}' không hỗ trợ. Chọn: {list(SUPPORTED_LANGUAGES.keys())}"
        )

    # Kiểm tra cache trước
    cached = get_cached_translation(poi_id, lang)
    if cached:
        return {**cached, "from_cache": True}

    # Lấy dữ liệu gốc từ Content Service
    poi = await get_poi_content(poi_id)

    # Áp dụng 3-tier fallback
    fallback_result = apply_3tier_fallback(poi, lang)

    # Nếu là tier 3 (chỉ có tiếng Việt) và request ngôn ngữ khác → dịch tự động
    if fallback_result["tier"] == 3 and lang not in ("vi",):
        translated_text = translate_text(
            fallback_result["text"],
            source_lang="vi",
            target_lang=lang
        )
        fallback_result["text"] = translated_text
        fallback_result["actual_lang"] = lang
        fallback_result["tier"] = 1  # Bây giờ đã có bản dịch
        fallback_result["is_fallback"] = False
        fallback_result["auto_translated"] = True

    # Tương tự cho tier 2 (tiếng Anh → ngôn ngữ khác)
    elif fallback_result["tier"] == 2 and lang not in ("en", "vi"):
        translated_text = translate_text(
            fallback_result["text"],
            source_lang="en",
            target_lang=lang
        )
        fallback_result["text"] = translated_text
        fallback_result["actual_lang"] = lang
        fallback_result["tier"] = 1
        fallback_result["is_fallback"] = False
        fallback_result["auto_translated"] = True

    # Xây dựng response đầy đủ
    result = {
        "poi_id": poi_id,
        "poi_name": poi.get("name", ""),
        "requested_lang": lang,
        "from_cache": False,
        **fallback_result
    }

    # Lưu vào cache
    save_to_cache(poi_id, lang, result)

    return result


@app.post("/translate")
async def translate_custom_text(text: str, source: str = "vi", target: str = "en"):
    if target not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Ngôn ngữ '{target}' không hỗ trợ")
    if source not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Ngôn ngữ nguồn '{source}' không hỗ trợ")

    translated = translate_text(text, source_lang=source, target_lang=target)

    return {
        "original": text,
        "source_language": source,
        "target_language": target,
        "translated": translated
    }


@app.get("/cache/stats")
def get_cache_stats():
    return {
        "total_cached": len(translation_cache),
        "cached_entries": list(translation_cache.keys())
    }


@app.delete("/cache")
def clear_cache():
    count = len(translation_cache)
    translation_cache.clear()
    return {"message": f"Đã xóa {count} bản dịch trong cache"}
