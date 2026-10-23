"""
Test Audio Service (giai đoạn 3). Chạy: pytest -v
Mock TTS (không gọi Edge TTS thật) và mock Content Service; không cần MongoDB.
"""
import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("AUDIO_DIR", "/tmp/audio_files")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32bytes-for-pytest!!")

import asyncio
import copy
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main as audio_main
from jwt_auth import JWT_ALGORITHM, JWT_SECRET, set_ticket_lookup
from main import VOICE_MAP, app, pick_poi_content

real_generate_tts_audio = audio_main.generate_tts_audio  # bản thật, dùng để test chọn giọng

client = TestClient(app)

LANGS = ("vi", "en", "zh", "ja", "ko")

POI = {
    "id": "p1",
    "name": "Cổng Chính",
    "translations": {
        "vi": {"name": "Cổng Chính", "description": "Mô tả tiếng Việt."},
        "en": {"name": "Main Gate", "description": "English description."},
        "zh": {"name": "正门", "description": "中文介绍。"},
        "ja": {"name": "正門", "description": "日本語の説明。"},
        "ko": {"name": "정문", "description": "한국어 설명입니다."},
    },
}


# ---------- helpers ----------

def _jwt(payload: dict, hours: float = 1) -> str:
    payload = {**payload, "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def staff(role="admin"):
    return {"Authorization": "Bearer " + _jwt({"type": "staff", "sub": "u1", "username": role, "role": role})}


def ticket(ticket_id="t1", version=1, hours=1):
    token = _jwt({"type": "ticket", "sub": ticket_id, "ticket_id": ticket_id, "token_version": version}, hours)
    return {"Authorization": f"Bearer {token}"}


class FakeTTS:
    def __init__(self):
        self.calls = []  # (text, language)
        self.delay = 0.0
        self.fail_langs = set()
        self.status_during = []  # snapshot trạng thái track lúc đang sinh

    async def __call__(self, text, language, output_path):
        self.calls.append((text, language))
        self.status_during.append({k: v["status"] for k, v in audio_main._tracks.items()})
        if self.delay:
            await asyncio.sleep(self.delay)
        if language in self.fail_langs:
            raise RuntimeError("tts boom")
        with open(output_path, "wb") as f:
            f.write(b"ID3fake-" + language.encode())


@pytest.fixture
def env(monkeypatch, tmp_path):
    poi = copy.deepcopy(POI)
    tts = FakeTTS()

    async def fake_get_poi(poi_id):
        if poi_id != poi["id"] and poi_id != "p10":
            raise HTTPException(status_code=404, detail="không có")
        return poi if poi_id == poi["id"] else {**poi, "id": "p10"}

    async def fake_ticket_lookup(ticket_id):
        return {"id": ticket_id, "token_version": 1} if ticket_id == "t1" else None

    monkeypatch.setattr(audio_main, "AUDIO_DIR", str(tmp_path))
    monkeypatch.setattr(audio_main, "get_poi_from_content_service", fake_get_poi)
    monkeypatch.setattr(audio_main, "generate_tts_audio", tts)
    monkeypatch.setattr(audio_main, "_tracks", {})
    monkeypatch.setattr(audio_main, "_locks", {})
    set_ticket_lookup(fake_ticket_lookup)

    class Env:
        pass

    e = Env()
    e.poi, e.tts, e.dir = poi, tts, tmp_path
    return e


def mp3_files(env, prefix=""):
    return sorted(f for f in os.listdir(env.dir) if f.endswith(".mp3") and f.startswith(prefix))


# ---------- giọng đọc & nội dung đúng ngôn ngữ ----------

def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_each_language_has_its_own_native_voice():
    assert set(VOICE_MAP) == set(LANGS)
    prefixes = {"vi": "vi-VN", "en": "en-", "zh": "zh-CN", "ja": "ja-JP", "ko": "ko-KR"}
    for lang, prefix in prefixes.items():
        assert VOICE_MAP[lang].startswith(prefix), (lang, VOICE_MAP[lang])
    assert len(set(VOICE_MAP.values())) == 5


def test_pick_content_uses_translation_of_same_language_only():
    for lang in LANGS:
        name, text, got_lang, voice = pick_poi_content(POI, lang)
        assert name == POI["translations"][lang]["name"]
        assert text == POI["translations"][lang]["description"]
        assert got_lang == lang and voice == VOICE_MAP[lang]


def test_pick_content_never_falls_back_to_another_language():
    only_vi = {"name": "Điểm", "translations": {"vi": {"name": "Điểm", "description": "Chỉ có tiếng Việt"}}}
    assert pick_poi_content(only_vi, "en") is None
    assert pick_poi_content(only_vi, "ja") is None
    assert pick_poi_content(POI, "fr") is None


@pytest.mark.parametrize("lang", LANGS)
def test_real_generate_uses_matching_voice(monkeypatch, tmp_path, lang):
    used = {}

    class FakeCommunicate:
        def __init__(self, text, voice):
            used["text"], used["voice"] = text, voice

        async def save(self, path):
            with open(path, "wb") as f:
                f.write(b"ID3")

    monkeypatch.setattr(audio_main.edge_tts, "Communicate", FakeCommunicate)
    out = str(tmp_path / "x.mp3")
    asyncio.run(real_generate_tts_audio("xin chào", lang, out))
    assert used["voice"] == VOICE_MAP[lang]
    assert os.path.exists(out) and not os.path.exists(out + ".tmp")


def test_real_generate_cleans_tmp_on_failure(monkeypatch, tmp_path):
    class Boom:
        def __init__(self, text, voice):
            pass

        async def save(self, path):
            with open(path, "wb") as f:
                f.write(b"partial")
            raise RuntimeError("network")

    monkeypatch.setattr(audio_main.edge_tts, "Communicate", Boom)
    out = str(tmp_path / "x.mp3")
    with pytest.raises(RuntimeError):
        asyncio.run(real_generate_tts_audio("hi", "en", out))
    assert not os.path.exists(out) and not os.path.exists(out + ".tmp")


# ---------- vé (ticket_token) ----------

def test_visitor_audio_without_ticket_is_401(env):
    assert client.get("/audio/poi/p1?lang=vi").status_code == 401
    assert env.tts.calls == []


def test_visitor_audio_rejects_staff_token_and_garbage(env):
    assert client.get("/audio/poi/p1?lang=vi", headers=staff("admin")).status_code == 401
    assert client.get("/audio/poi/p1?lang=vi", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401
    assert env.tts.calls == []


def test_visitor_audio_rejects_expired_unknown_and_replaced_ticket(env):
    assert client.get("/audio/poi/p1?lang=vi", headers=ticket(hours=-1)).status_code == 401
    assert client.get("/audio/poi/p1?lang=vi", headers=ticket("khong-co")).status_code == 401
    assert client.get("/audio/poi/p1?lang=vi", headers=ticket(version=0)).status_code == 401  # đã đổi máy
    assert env.tts.calls == []


@pytest.mark.parametrize("lang", LANGS)
def test_visitor_gets_audio_in_each_language(env, lang):
    r = client.get(f"/audio/poi/p1?lang={lang}", headers=ticket())
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3fake-" + lang.encode()
    tr = POI["translations"][lang]
    assert env.tts.calls == [(f"{tr['name']}. {tr['description']}", lang)]


def test_visitor_audio_errors(env):
    h = ticket()
    assert client.get("/audio/poi/p1?lang=fr", headers=h).status_code == 400
    assert client.get("/audio/poi/khong-co?lang=vi", headers=h).status_code == 404
    del env.poi["translations"]["ko"]
    assert client.get("/audio/poi/p1?lang=ko", headers=h).status_code == 404  # không đọc thay bằng tiếng khác
    assert env.tts.calls == []


# ---------- cache MD5 & sinh lại khi đổi nội dung ----------

def test_cache_hit_and_md5_filename(env):
    h = ticket()
    assert client.get("/audio/poi/p1?lang=vi", headers=h).status_code == 200
    assert client.get("/audio/poi/p1?lang=vi", headers=h).status_code == 200
    assert len(env.tts.calls) == 1
    digest = hashlib.md5(f"Cổng Chính. Mô tả tiếng Việt.|vi|{VOICE_MAP['vi']}".encode("utf-8")).hexdigest()
    assert mp3_files(env) == [f"p1_vi_{digest}.mp3"]


def test_editing_description_regenerates_only_that_language(env):
    h = ticket()
    for lang in ("vi", "en"):
        client.get(f"/audio/poi/p1?lang={lang}", headers=h)
    assert len(env.tts.calls) == 2
    env.poi["translations"]["en"]["description"] = "Updated English text."
    client.get("/audio/poi/p1?lang=en", headers=h)
    client.get("/audio/poi/p1?lang=vi", headers=h)
    assert len(env.tts.calls) == 3
    assert env.tts.calls[-1][1] == "en" and "Updated English text." in env.tts.calls[-1][0]
    assert len(mp3_files(env, "p1_en_")) == 1  # file cũ đã được dọn
    assert len(mp3_files(env, "p1_vi_")) == 1


def test_concurrent_requests_generate_once(env):
    env.tts.delay = 0.05

    async def run():
        return await asyncio.gather(*[audio_main.ensure_poi_audio("p1", "vi") for _ in range(10)])

    results = asyncio.run(run())
    assert len(env.tts.calls) == 1
    assert all(r["status"] == "ready" for r in results)
    assert len({r["filename"] for r in results}) == 1
    assert sum(1 for r in results if not r["cached"]) == 1
    assert env.tts.status_during[0][("p1", "vi")] == "generating"


def test_concurrent_requests_for_different_languages_are_independent(env):
    env.tts.delay = 0.02

    async def run():
        return await asyncio.gather(
            *[audio_main.ensure_poi_audio("p1", lang) for lang in LANGS for _ in range(3)]
        )

    asyncio.run(run())
    assert sorted(lang for _, lang in env.tts.calls) == sorted(LANGS)


# ---------- trạng thái audio ----------

def test_status_ready_after_generation_and_admin_only(env):
    client.get("/audio/poi/p1?lang=ja", headers=ticket())
    assert client.get("/audio/status/p1").status_code == 401
    assert client.get("/audio/status/p1", headers=staff("counter")).status_code == 403
    assert client.get("/audio/status/p1", headers=ticket()).status_code == 401
    st = client.get("/audio/status/p1", headers=staff("admin")).json()["audio_status"]
    assert st["ja"]["status"] == "ready" and st["ja"]["voice"] == VOICE_MAP["ja"]
    assert st["vi"]["status"] == "pending"


def test_tts_failure_marks_error_then_recovers(env):
    env.tts.fail_langs.add("zh")
    r = client.get("/audio/poi/p1?lang=zh", headers=ticket())
    assert r.status_code == 502
    st = client.get("/audio/status/p1", headers=staff("admin")).json()["audio_status"]
    assert st["zh"]["status"] == "error"
    assert mp3_files(env, "p1_zh_") == []
    env.tts.fail_langs.clear()
    assert client.get("/audio/poi/p1?lang=zh", headers=ticket()).status_code == 200
    st = client.get("/audio/status/p1", headers=staff("admin")).json()["audio_status"]
    assert st["zh"]["status"] == "ready"


def test_admin_preview(env):
    assert client.get("/audio/preview/p1?lang=en").status_code == 401
    assert client.get("/audio/preview/p1?lang=en", headers=ticket()).status_code == 401
    assert client.get("/audio/preview/p1?lang=en", headers=staff("counter")).status_code == 403
    r = client.get("/audio/preview/p1?lang=en", headers=staff("admin"))
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"


# ---------- sinh nền / nội bộ ----------

def test_generate_langs_skips_missing_and_survives_errors(env):
    del env.poi["translations"]["ko"]
    env.tts.fail_langs.add("ja")
    asyncio.run(audio_main._generate_langs("p1", None))
    assert audio_main._tracks[("p1", "ja")]["status"] == "error"
    for lang in ("vi", "en", "zh"):
        assert audio_main._tracks[("p1", lang)]["status"] == "ready"
    assert ("p1", "ko") not in audio_main._tracks


def test_generate_langs_only_requested_languages(env):
    asyncio.run(audio_main._generate_langs("p1", ["en"]))
    assert [lang for _, lang in env.tts.calls] == ["en"]


def test_internal_endpoints_require_service_key(env, monkeypatch):
    async def noop(poi_id, languages):
        return None

    monkeypatch.setattr(audio_main, "_generate_langs", noop)
    assert client.post("/internal/generate", json={"poi_id": "p1"}).status_code == 401
    bad = {"X-Internal-Key": "sai"}
    assert client.post("/internal/generate", json={"poi_id": "p1"}, headers=bad).status_code == 401
    assert client.post("/internal/warmup", headers=bad).status_code == 401
    assert client.delete("/internal/pois/p1", headers=bad).status_code == 401
    # JWT admin cũng không thay được service key
    assert client.post("/internal/generate", json={"poi_id": "p1"}, headers=staff("admin")).status_code == 401
    good = {"X-Internal-Key": audio_main.INTERNAL_SERVICE_KEY}
    r = client.post("/internal/generate", json={"poi_id": "p1", "languages": ["en"]}, headers=good)
    assert r.status_code == 200 and r.json()["status"] == "accepted"


def test_internal_delete_removes_only_that_poi(env):
    for pid in ("p1", "p10"):
        for lang in ("vi", "en"):
            asyncio.run(audio_main.ensure_poi_audio(pid, lang))
    assert len(mp3_files(env, "p1_")) == 2 and len(mp3_files(env, "p10_")) == 2
    good = {"X-Internal-Key": audio_main.INTERNAL_SERVICE_KEY}
    r = client.delete("/internal/pois/p1", headers=good)
    assert r.status_code == 200 and len(r.json()["deleted_files"]) == 2
    assert mp3_files(env, "p1_") == [] and len(mp3_files(env, "p10_")) == 2
    assert not any(k[0] == "p1" for k in audio_main._tracks)


# ---------- file/endpoint công cụ không được bypass vé ----------

def test_tts_download_and_list_are_admin_only(env):
    body = {"text": "xin chào", "language": "vi"}
    assert client.post("/tts", json=body).status_code == 401
    assert client.post("/tts", json=body, headers=ticket()).status_code == 401
    assert client.post("/tts", json=body, headers=staff("counter")).status_code == 403
    r = client.post("/tts", json=body, headers=staff("admin"))
    assert r.status_code == 200 and r.json()["voice_used"] == VOICE_MAP["vi"]
    filename = r.json()["audio_url"].rsplit("/", 1)[1]
    assert client.get(f"/audio/download/{filename}").status_code == 401
    assert client.get(f"/audio/download/{filename}", headers=ticket()).status_code == 401
    assert client.get(f"/audio/download/{filename}", headers=staff("admin")).status_code == 200
    assert client.get("/audio/list").status_code == 401
    assert client.get("/audio/list", headers=staff("admin")).status_code == 200


def test_tts_and_download_validation(env):
    h = staff("admin")
    assert client.post("/tts", json={"text": "x", "language": "fr"}, headers=h).status_code == 400
    assert client.post("/tts", json={"text": "x" * 5001, "language": "vi"}, headers=h).status_code == 400
    assert client.get("/audio/download/abc.txt", headers=h).status_code == 400
    assert client.get("/audio/download/khong-co.mp3", headers=h).status_code == 404
