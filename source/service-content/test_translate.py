"""Test cho endpoint /translate của Content Service."""

import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32bytes-for-pytest!!")

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import main
import translator
from jwt_auth import JWT_ALGORITHM, JWT_SECRET

client = TestClient(main.app)


def _staff_token(role: str, username: str = "tester") -> str:
    return jwt.encode(
        {
            "type": "staff",
            "sub": "uid-test",
            "username": username,
            "role": role,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def admin_headers():
    return {"Authorization": f"Bearer {_staff_token('admin')}"}


def counter_headers():
    return {"Authorization": f"Bearer {_staff_token('counter')}"}


def test_translate_admin_success(monkeypatch):
    """Admin dịch thành công đủ 4 ngôn ngữ en, zh, ja, ko."""
    def fake_translate(text: str, lang: str) -> str:
        return f"[{lang}] {text}"

    monkeypatch.setattr(translator, "translate_text", fake_translate)

    body = {
        "name": "Hổ Bengal",
        "description": "Loài hổ quý hiếm tại Thảo Cầm Viên.",
    }
    resp = client.post("/translate", json=body, headers=admin_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert "translations" in data
    trans = data["translations"]
    for lang in ("en", "zh", "ja", "ko"):
        assert lang in trans
        assert trans[lang]["name"] == f"[{lang}] Hổ Bengal"
        assert trans[lang]["description"] == f"[{lang}] Loài hổ quý hiếm tại Thảo Cầm Viên."


def test_translate_counter_forbidden(monkeypatch):
    """Counter không có quyền gọi endpoint /translate (403)."""
    resp = client.post(
        "/translate",
        json={"name": "Hổ Bengal", "description": "Mô tả"},
        headers=counter_headers(),
    )
    assert resp.status_code == 403


def test_translate_no_token_unauthorized():
    """Không có token thì bị từ chối 401."""
    resp = client.post("/translate", json={"name": "Hổ Bengal", "description": "Mô tả"})
    assert resp.status_code == 401


def test_translate_validation_errors():
    """Tên hoặc mô tả rỗng sau strip hoặc vượt quá độ dài tối đa -> 400."""
    # name rỗng
    r1 = client.post("/translate", json={"name": "   ", "description": "Mô tả hợp lệ"}, headers=admin_headers())
    assert r1.status_code == 400

    # description rỗng
    r2 = client.post("/translate", json={"name": "Tên hợp lệ", "description": ""}, headers=admin_headers())
    assert r2.status_code == 400

    # name vượt quá 200 ký tự
    r3 = client.post("/translate", json={"name": "A" * 201, "description": "Mô tả hợp lệ"}, headers=admin_headers())
    assert r3.status_code == 400

    # description vượt quá 4500 ký tự
    r4 = client.post("/translate", json={"name": "Tên hợp lệ", "description": "A" * 4501}, headers=admin_headers())
    assert r4.status_code == 400


def test_translate_error_returns_502(monkeypatch):
    """Khi hàm dịch ném Exception -> trả 502 với message chung."""
    def failing_translate(text: str, lang: str) -> str:
        raise RuntimeError("Google Translate connection error")

    monkeypatch.setattr(translator, "translate_text", failing_translate)

    body = {
        "name": "Hổ Bengal",
        "description": "Loài hổ quý hiếm.",
    }
    resp = client.post("/translate", json=body, headers=admin_headers())
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Không dịch được, vui lòng thử lại sau"
