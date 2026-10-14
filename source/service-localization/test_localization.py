import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app, translation_cache, apply_3tier_fallback

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_cache():
    translation_cache.clear()
    yield
    translation_cache.clear()

# Test 1: Service cơ bản
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Localization Service"
    assert "supported_languages" in data


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_languages():
    response = client.get("/languages")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    langs = data["languages"]
    assert "vi" in langs
    assert "en" in langs
    assert "zh" in langs
    assert "ja" in langs
    assert "ko" in langs

# Test 2: 3-Tier Fallback Logic
def test_tier1_returns_requested_language():
    poi = {
        "name": "Cổng Chính",
        "description_vi": "Mô tả tiếng Việt",
        "description_en": "Main Gate description in English"
    }
    result = apply_3tier_fallback(poi, "en")
    assert result["tier"] == 1
    assert result["actual_lang"] == "en"
    assert result["is_fallback"] == False
    assert "English" in result["text"]


def test_tier1_vietnamese():
    poi = {
        "name": "Cổng Chính",
        "description_vi": "Mô tả tiếng Việt",
        "description_en": "English description"
    }
    result = apply_3tier_fallback(poi, "vi")
    assert result["tier"] == 1
    assert result["actual_lang"] == "vi"
    assert result["is_fallback"] == False


def test_tier2_english_fallback():
    poi = {
        "name": "Cổng Chính",
        "description_vi": "Mô tả tiếng Việt",
        "description_en": "English description"
        # Không có description_ja!
    }
    result = apply_3tier_fallback(poi, "ja")
    assert result["tier"] == 2
    assert result["actual_lang"] == "en"       # Đã fallback sang EN
    assert result["is_fallback"] == True        # Đánh dấu là fallback
    assert result["fallback_reason"] is not None


def test_tier3_vietnamese_fallback():
    poi = {
        "name": "Cổng Chính",
        "description_vi": "Mô tả tiếng Việt gốc"
        # Không có description_en và description_ko!
    }
    result = apply_3tier_fallback(poi, "ko")
    assert result["tier"] == 3
    assert result["actual_lang"] == "vi"        # Fallback về Việt
    assert result["is_fallback"] == True
    assert "tiếng Việt" in result["text"]


def test_tier1_prefers_exact_match():
    poi = {
        "name": "Test",
        "description_vi": "Tiếng Việt",
        "description_en": "English",
        "description_zh": "中文内容"   # Có tiếng Trung!
    }
    result = apply_3tier_fallback(poi, "zh")
    assert result["tier"] == 1          # Phải là tier 1
    assert result["actual_lang"] == "zh"  # Đúng tiếng Trung
    assert "中文" in result["text"]

# Test 3: Cache
def test_cache_is_empty_initially():
    response = client.get("/cache/stats")
    assert response.status_code == 200
    assert response.json()["total_cached"] == 0


def test_clear_cache():
    response = client.delete("/cache")
    assert response.status_code == 200
    assert "Đã xóa" in response.json()["message"]

# Test 4: Validate ngôn ngữ không hỗ trợ
def test_unsupported_language_returns_400():
    # Mock get_poi_content để không cần Content Service
    with patch("main.get_poi_content") as mock:
        mock.return_value = {
            "id": "tcv-001",
            "name": "Test",
            "description_vi": "Test"
        }
        response = client.get("/poi/tcv-001?lang=xx")  # xx không tồn tại
    assert response.status_code == 400
