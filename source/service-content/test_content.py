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


def test_nearby_invalid_coords_return_422(client):
    invalid_cases = [
        "lat=91&lon=106",
        "lat=-91&lon=106",
        "lat=10&lon=181",
        "lat=inf&lon=106",
        "lat=nan&lon=106",
        "lat=10&lon=nan",
    ]
    for route in ["/pois/nearby", "/pois/nearby/search"]:
        for query in invalid_cases:
            res = client.get(f"{route}?{query}")
            assert res.status_code == 422, f"Failed for {route}?{query}: got {res.status_code}"


def test_nearby_alias_radius_validation(client):
    for r in [0, -5]:
        res = client.get(f"/pois/nearby/search?lat={GATE[0]}&lon={GATE[1]}&radius_m={r}")
        assert res.status_code == 422, f"Expected 422 for radius_m={r}, got {res.status_code}"


def test_nearby_boundary_exact_and_sub_half_meter(client):
    from events_core import haversine_m
    search_pt = (10.788, 106.706)
    d = haversine_m(search_pt[0], search_pt[1], GATE[0], GATE[1])

    # Bán kính = d: tcv-001 có trong kết quả (cả 2 route)
    res_nearby = client.get(f"/pois/nearby?lat={search_pt[0]}&lon={search_pt[1]}&search_radius_m={d}")
    assert res_nearby.status_code == 200
    assert "tcv-001" in [p["id"] for p in res_nearby.json()["pois"]]

    res_alias = client.get(f"/pois/nearby/search?lat={search_pt[0]}&lon={search_pt[1]}&radius_m={d}")
    assert res_alias.status_code == 200
    assert "tcv-001" in [p["id"] for p in res_alias.json()["pois"]]

    # Bán kính = d - 0.5: tcv-001 không có trong kết quả
    res_nearby_less = client.get(f"/pois/nearby?lat={search_pt[0]}&lon={search_pt[1]}&search_radius_m={d - 0.5}")
    assert res_nearby_less.status_code == 200
    assert "tcv-001" not in [p["id"] for p in res_nearby_less.json()["pois"]]

    res_alias_less = client.get(f"/pois/nearby/search?lat={search_pt[0]}&lon={search_pt[1]}&radius_m={d - 0.5}")
    assert res_alias_less.status_code == 200
    assert "tcv-001" not in [p["id"] for p in res_alias_less.json()["pois"]]


def test_haversine_accuracy_precision():
    from events_core import haversine_m
    d = haversine_m(10, 106, 10.001, 106)
    assert 111.19 - 0.05 <= d <= 111.19 + 0.05


def test_nearby_skips_corrupted_poi_without_exception(client):
    store = main.get_store()
    corrupt_poi = {
        "id": "corrupt-poi",
        "category": "tien_ich",
        "lat": "not_a_float",
        "lon": None,
        "radius_m": 20,
        "translations": {"vi": {"name": "Lỗi", "description": "Lỗi"}},
    }
    store.docs["corrupt-poi"] = corrupt_poi
    res = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=300")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()["pois"]]
    assert "corrupt-poi" not in ids
    assert "tcv-001" in ids


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


def test_nearby_max_search_radius_100000(client):
    # 100000 -> 200 và trả về mọi POI (PRD UC02 quy định 'Tất cả' = 100.000m)
    r1 = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=100000")
    assert r1.status_code == 200
    all_pois = client.get("/pois").json()["pois"]
    assert len(r1.json()["pois"]) == len(all_pois)

    # alias route cũng nhận 100000
    r1_alias = client.get(f"/pois/nearby/search?lat={GATE[0]}&lon={GATE[1]}&radius_m=100000")
    assert r1_alias.status_code == 200
    assert len(r1_alias.json()["pois"]) == len(all_pois)

    # 100001 -> 422
    assert client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=100001").status_code == 422
    assert client.get(f"/pois/nearby/search?lat={GATE[0]}&lon={GATE[1]}&radius_m=100001").status_code == 422

    # 0, âm, NaN, inf -> 422
    for bad in ["0", "-1", "-100", "nan", "inf"]:
        assert client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m={bad}").status_code == 422
        assert client.get(f"/pois/nearby/search?lat={GATE[0]}&lon={GATE[1]}&radius_m={bad}").status_code == 422


def test_nearby_poi_missing_radius_m_defaults_to_30(client):
    store = main.get_store()
    poi_no_rad = {
        "id": "poi-no-radius",
        "category": "dong_vat",
        "lat": GATE[0],
        "lon": GATE[1],
        "translations": {"vi": {"name": "Không radius", "description": "Mặc định 30m"}},
    }
    store.docs["poi-no-radius"] = poi_no_rad

    # Tìm kiếm cách đó ~11m -> within_poi_radius phải là True (11 <= 30)
    lat_10m = GATE[0] + 0.0001
    res = client.get(f"/pois/nearby?lat={lat_10m}&lon={GATE[1]}&search_radius_m=50")
    assert res.status_code == 200
    p = next((x for x in res.json()["pois"] if x["id"] == "poi-no-radius"), None)
    assert p is not None
    assert p["within_poi_radius"] is True

    # Tìm kiếm cách đó ~39m -> within_poi_radius phải là False (39 > 30)
    lat_35m = GATE[0] + 0.00035
    res2 = client.get(f"/pois/nearby?lat={lat_35m}&lon={GATE[1]}&search_radius_m=50")
    assert res2.status_code == 200
    p2 = next((x for x in res2.json()["pois"] if x["id"] == "poi-no-radius"), None)
    assert p2 is not None
    assert p2["within_poi_radius"] is False

    # POI có radius_m <= 0 hoặc không phải số thì bị bỏ qua và log warning
    store.docs["poi-zero-rad"] = {
        "id": "poi-zero-rad",
        "category": "dong_vat",
        "lat": GATE[0],
        "lon": GATE[1],
        "radius_m": 0,
        "translations": {"vi": {"name": "Zero radius", "description": "Bị bỏ qua"}},
    }
    res3 = client.get(f"/pois/nearby?lat={GATE[0]}&lon={GATE[1]}&search_radius_m=50")
    ids = [x["id"] for x in res3.json()["pois"]]
    assert "poi-zero-rad" not in ids


def test_poi_not_found_structured_error(client):
    h = admin()

    # GET /pois/{id}
    r_get = client.get("/pois/khong-ton-tai")
    assert r_get.status_code == 404
    assert r_get.json()["detail"]["error"] == "poi_not_found"
    assert "Không tìm thấy" in r_get.json()["detail"]["message"]

    # GET /pois/{id}/audio-status
    r_audio = client.get("/pois/khong-ton-tai/audio-status", headers=h)
    assert r_audio.status_code == 404
    assert r_audio.json()["detail"]["error"] == "poi_not_found"

    # PUT /pois/{id}
    r_put = client.put("/pois/khong-ton-tai", json={"name": "Test"}, headers=h)
    assert r_put.status_code == 404
    assert r_put.json()["detail"]["error"] == "poi_not_found"

    # PATCH /pois/{id}/translations/{lang}
    r_patch = client.patch("/pois/khong-ton-tai/translations/en", json={"name": "Test"}, headers=h)
    assert r_patch.status_code == 404
    assert r_patch.json()["detail"]["error"] == "poi_not_found"

    # DELETE /pois/{id}
    r_del = client.delete("/pois/khong-ton-tai", headers=h)
    assert r_del.status_code == 404
    assert r_del.json()["detail"]["error"] == "poi_not_found"
