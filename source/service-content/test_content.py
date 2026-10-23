"""
Test Content Service (giai đoạn 3). Chạy: pytest -v
Dùng MemoryPoiStore + seed/pois.json (TESTING=1), không cần MongoDB hay Audio Service.
"""
import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32bytes-for-pytest!!")

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import main
from jwt_auth import JWT_ALGORITHM, JWT_SECRET
from poi_store import CATEGORIES, LANGS

GATE = (10.78755, 106.70528)  # tcv-001 trong seed


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


def _ticket_token() -> str:
    return jwt.encode(
        {
            "type": "ticket",
            "sub": "t1",
            "ticket_id": "t1",
            "token_version": 1,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def admin():
    return {"Authorization": f"Bearer {_staff_token('admin')}"}


def counter():
    return {"Authorization": f"Bearer {_staff_token('counter')}"}


def new_poi(**over):
    body = {
        "lat": 10.79,
        "lon": 106.71,
        "radius_m": 20,
        "category": "tien_ich",
        "translations": {
            "vi": {"name": "Khu Demo", "description": "Mô tả tiếng Việt. Câu hai."},
            "en": {"name": "Demo Zone", "description": "English description. Second sentence."},
        },
    }
    body.update(over)
    return body


@pytest.fixture
def client(monkeypatch):
    """Client mới + store seed mới cho mỗi test; ghi lại các lần gọi Audio Service."""
    calls = {"generate": [], "delete": []}

    async def fake_generate(poi_id, languages=None):
        calls["generate"].append((poi_id, list(languages or [])))

    async def fake_delete(poi_id):
        calls["delete"].append(poi_id)

    monkeypatch.setattr(main, "generate_poi_audio", fake_generate)
    monkeypatch.setattr(main, "delete_poi_audio", fake_delete)
    with TestClient(main.app) as c:
        c.audio_calls = calls
        yield c


# ---------- Seed dữ liệu ----------

def test_root_and_health(client):
    assert client.get("/health").json()["status"] == "ok"
    data = client.get("/").json()
    assert data["service"] == "Content Service"
    assert data["total_pois"] >= 15


def test_seed_has_at_least_15_pois_with_valid_fields(client):
    pois = client.get("/pois").json()["pois"]
    assert len(pois) >= 15
    ids = [p["id"] for p in pois]
    assert len(ids) == len(set(ids)), "id POI bị trùng"
    for p in pois:
        assert p["category"] in CATEGORIES, p["id"]
        assert p["radius_m"] > 0, p["id"]
        # tọa độ nằm quanh Thảo Cầm Viên (Q.1, TP.HCM)
        assert 10.78 < p["lat"] < 10.80 and 106.70 < p["lon"] < 106.72, p["id"]


def test_seed_has_all_five_translations(client):
    for p in client.get("/pois").json()["pois"]:
        for lang in LANGS:
            tr = p["translations"].get(lang) or {}
            assert tr.get("name") and tr.get("description"), f"{p['id']} thiếu bản dịch {lang}"


def test_seed_covers_every_category(client):
    cats = {p["category"] for p in client.get("/pois").json()["pois"]}
    assert cats == CATEGORIES


# ---------- Đọc công khai (không cần vé) ----------

def test_public_reads_need_no_token(client):
    assert client.get("/pois").status_code == 200
    assert client.get("/pois/tcv-001").status_code == 200
    assert client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}").status_code == 200


def test_get_poi_not_found(client):
    assert client.get("/pois/khong-ton-tai").status_code == 404


def test_filter_by_category(client):
    data = client.get("/pois?category=chim").json()
    assert data["total"] >= 1
    assert all(p["category"] == "chim" for p in data["pois"])


def test_public_responses_hide_audio_status(client):
    assert "audio_status" not in client.get("/pois/tcv-001").json()
    assert all("audio_status" not in p for p in client.get("/pois").json()["pois"])
    near = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=300").json()
    assert all("audio_status" not in p for p in near["pois"])


# ---------- Nearby ----------

def test_haversine_known_distance():
    # 0.001° kinh độ ở vĩ độ 10° ≈ 109.5 m
    assert main.calculate_distance(10.0, 106.0, 10.0, 106.001) == pytest.approx(109.5, abs=1.0)
    assert main.calculate_distance(10.0, 106.0, 10.0, 106.0) == 0


def test_nearby_sorted_nearest_first(client):
    data = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=300").json()
    assert data["found"] > 1
    distances = [p["distance_m"] for p in data["pois"]]
    assert distances == sorted(distances)
    assert data["pois"][0]["id"] == "tcv-001"
    assert data["pois"][0]["distance_m"] == 0
    assert all(d <= 300 for d in distances)


def test_nearby_names_search_radius_and_poi_radius_separately(client):
    data = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=120").json()
    assert data["search_radius_m"] == 120
    gate = data["pois"][0]
    assert "radius_m" in gate  # vùng kích hoạt riêng của POI
    assert gate["within_poi_radius"] is True


def test_nearby_within_poi_radius_false_when_outside_activation_zone(client):
    # đứng cách Cổng Chính ~55 m: nằm trong search 100 m nhưng ngoài radius_m (35 m)
    lat = GATE[0] + 0.0005
    data = client.get(f"/pois/nearby?lat={lat}&lon={GATE[1]}&search_radius_m=100").json()
    gate = next(p for p in data["pois"] if p["id"] == "tcv-001")
    assert 35 < gate["distance_m"] <= 100
    assert gate["within_poi_radius"] is False


def test_nearby_no_result_far_away(client):
    data = client.get("/pois/nearby?lat=0&lon=0&search_radius_m=50").json()
    assert data["found"] == 0 and data["pois"] == []


def test_nearby_rejects_non_positive_search_radius(client):
    assert client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=0").status_code == 422


def test_nearby_requires_lat_lon(client):
    assert client.get("/pois/nearby").status_code == 422


# ---------- Quyền CRUD ----------

def test_write_endpoints_without_token_are_401(client):
    assert client.post("/pois", json=new_poi()).status_code == 401
    assert client.put("/pois/tcv-001", json={"radius_m": 10}).status_code == 401
    assert client.patch("/pois/tcv-001/translations/en", json={"name": "X"}).status_code == 401
    assert client.delete("/pois/tcv-001").status_code == 401
    assert client.get("/pois/tcv-001/audio-status").status_code == 401


def test_write_endpoints_as_counter_are_403(client):
    h = counter()
    assert client.post("/pois", json=new_poi(), headers=h).status_code == 403
    assert client.put("/pois/tcv-001", json={"radius_m": 10}, headers=h).status_code == 403
    assert client.patch("/pois/tcv-001/translations/en", json={"name": "X"}, headers=h).status_code == 403
    assert client.delete("/pois/tcv-001", headers=h).status_code == 403
    assert client.get("/pois/tcv-001/audio-status", headers=h).status_code == 403
    assert client.get("/pois/tcv-001").status_code == 200  # không bị xóa
    assert client.audio_calls["generate"] == [] and client.audio_calls["delete"] == []


def test_ticket_token_cannot_write(client):
    h = {"Authorization": f"Bearer {_ticket_token()}"}
    assert client.post("/pois", json=new_poi(), headers=h).status_code == 401
    assert client.delete("/pois/tcv-001", headers=h).status_code == 401


# ---------- Tạo POI ----------

def test_admin_create_poi_triggers_audio_for_each_translated_language(client):
    r = client.post("/pois", json=new_poi(), headers=admin())
    assert r.status_code == 201
    poi = r.json()["poi"]
    assert poi["created_by"] == "tester"
    assert poi["name"] == "Khu Demo"  # lấy từ bản dịch vi
    assert poi["audio_status"]["vi"]["status"] == "pending"
    assert client.get(f"/pois/{poi['id']}").status_code == 200
    gen = client.audio_calls["generate"]
    assert len(gen) == 1 and gen[0][0] == poi["id"] and sorted(gen[0][1]) == ["en", "vi"]


def test_create_poi_validation(client):
    h = admin()
    assert client.post("/pois", json=new_poi(category="khong_co"), headers=h).status_code == 400
    no_vi = new_poi(translations={"en": {"name": "A", "description": "B"}})
    assert client.post("/pois", json=no_vi, headers=h).status_code == 400
    bad_lang = new_poi(translations={"vi": {"name": "A", "description": "B"}, "fr": {"name": "A", "description": "B"}})
    assert client.post("/pois", json=bad_lang, headers=h).status_code == 400
    assert client.post("/pois", json=new_poi(lat=123), headers=h).status_code == 422
    assert client.post("/pois", json=new_poi(radius_m=0), headers=h).status_code == 422
    empty_desc = new_poi(translations={"vi": {"name": "A", "description": ""}})
    assert client.post("/pois", json=empty_desc, headers=h).status_code == 422
    assert client.audio_calls["generate"] == []


# ---------- Sửa POI / bản dịch → sinh lại audio đúng ngôn ngữ ----------

def test_put_description_regenerates_only_changed_language(client):
    h = admin()
    poi = client.get("/pois/tcv-001").json()
    new_en = {"name": poi["translations"]["en"]["name"], "description": "A brand new English description."}
    r = client.put("/pois/tcv-001", json={"translations": {"en": new_en}}, headers=h)
    assert r.status_code == 200
    assert client.audio_calls["generate"] == [("tcv-001", ["en"])]
    after = r.json()["poi"]
    assert after["translations"]["en"]["description"] == new_en["description"]
    assert after["translations"]["ja"] == poi["translations"]["ja"]  # ngôn ngữ khác giữ nguyên
    assert after["audio_status"]["en"]["status"] == "pending"
    assert after["audio_status"]["vi"]["status"] == "pending"  # chưa ai sinh, vẫn là mặc định


def test_put_without_text_change_does_not_regenerate(client):
    r = client.put("/pois/tcv-001", json={"radius_m": 60, "category": "tien_ich"}, headers=admin())
    assert r.status_code == 200
    assert r.json()["poi"]["radius_m"] == 60
    assert client.audio_calls["generate"] == []


def test_put_resending_identical_translation_does_not_regenerate(client):
    same = client.get("/pois/tcv-001").json()["translations"]["zh"]
    client.put("/pois/tcv-001", json={"translations": {"zh": same}}, headers=admin())
    assert client.audio_calls["generate"] == []


def test_put_not_found_and_bad_category(client):
    assert client.put("/pois/khong-co", json={"radius_m": 10}, headers=admin()).status_code == 404
    assert client.put("/pois/tcv-001", json={"category": "xxx"}, headers=admin()).status_code == 400


def test_patch_single_translation_regenerates_that_language_only(client):
    r = client.patch("/pois/tcv-002/translations/ja", json={"description": "修正した説明文です。"}, headers=admin())
    assert r.status_code == 200
    assert r.json()["poi"]["translations"]["ja"]["description"] == "修正した説明文です。"
    assert r.json()["poi"]["audio_status"]["ja"]["status"] == "pending"
    assert client.audio_calls["generate"] == [("tcv-002", ["ja"])]


def test_patch_vi_name_updates_poi_name(client):
    r = client.patch("/pois/tcv-002/translations/vi", json={"name": "Khu Voi"}, headers=admin())
    assert r.json()["poi"]["name"] == "Khu Voi"
    assert client.audio_calls["generate"] == [("tcv-002", ["vi"])]


def test_patch_same_text_does_not_regenerate(client):
    cur = client.get("/pois/tcv-002").json()["translations"]["ko"]
    r = client.patch("/pois/tcv-002/translations/ko", json={"description": cur["description"]}, headers=admin())
    assert r.status_code == 200
    assert client.audio_calls["generate"] == []


def test_patch_translation_errors(client):
    h = admin()
    assert client.patch("/pois/tcv-002/translations/fr", json={"name": "X"}, headers=h).status_code == 400
    assert client.patch("/pois/tcv-002/translations/en", json={}, headers=h).status_code == 400
    assert client.patch("/pois/khong-co/translations/en", json={"name": "X"}, headers=h).status_code == 404
    assert client.patch("/pois/tcv-002/translations/en", json={"name": ""}, headers=h).status_code == 422


def test_admin_can_read_audio_status(client):
    r = client.get("/pois/tcv-001/audio-status", headers=admin())
    assert r.status_code == 200
    assert set(r.json()["audio_status"]) == set(LANGS)
    assert client.get("/pois/khong-co/audio-status", headers=admin()).status_code == 404


# ---------- Xóa POI ----------

def test_admin_delete_poi_cleans_up_audio(client):
    created = client.post("/pois", json=new_poi(), headers=admin()).json()["poi"]["id"]
    r = client.delete(f"/pois/{created}", headers=admin())
    assert r.status_code == 200
    assert client.get(f"/pois/{created}").status_code == 404
    assert client.audio_calls["delete"] == [created]


def test_delete_not_found(client):
    assert client.delete("/pois/khong-co", headers=admin()).status_code == 404
    assert client.audio_calls["delete"] == []
