"""
Audio Service — TTS đúng giọng từng ngôn ngữ, cache MD5, khóa sinh song song.
Database riêng: collection `audio_tracks`. Vé tra qua Auth Service, trạng thái audio báo về Content Service (HTTP nội bộ).
Du khách: GET /audio/poi/{id}?lang= cần ticket_token.
Admin: nghe thử + xem trạng thái.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import edge_tts
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from auth_client import fetch_ticket
from jwt_auth import require_roles, require_valid_ticket, set_ticket_lookup

log = logging.getLogger("audio")

CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://content-service:8002").rstrip("/")
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio_files")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27020")
DB_NAME = os.getenv("DB_NAME", "zoo_audio")
TESTING = os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
EDGE_TTS_TIMEOUT_SEC = float(os.getenv("EDGE_TTS_TIMEOUT_SEC", "45"))

_WEAK_INTERNAL_KEYS = {"internal-secret-change-me", "change-me-internal-key"}


def _load_internal_key() -> str:
    key = os.getenv("INTERNAL_SERVICE_KEY", "").strip()
    if TESTING:
        return key or "internal-secret-change-me"
    if len(key) < 16 or key in _WEAK_INTERNAL_KEYS:
        raise RuntimeError(
            "INTERNAL_SERVICE_KEY chưa đặt hoặc quá yếu (cần >= 16 ký tự, không dùng giá trị mẫu). "
            'Tạo bằng: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    return key


INTERNAL_SERVICE_KEY = _load_internal_key()

VOICE_MAP = {
    "vi": "vi-VN-HoaiMyNeural",
    "en": "en-US-JennyNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}

os.makedirs(AUDIO_DIR, exist_ok=True)

db_client: Optional[AsyncIOMotorClient] = None
_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()
_tracks: dict[tuple[str, str], dict] = {}
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client
    if TESTING:
        yield
        return
    db_client = AsyncIOMotorClient(MONGO_URI)
    db = db_client[DB_NAME]
    await db["audio_tracks"].create_index([("poi_id", 1), ("lang", 1)], unique=True)

    set_ticket_lookup(fetch_ticket)  # vé thuộc database của Auth Service
    yield
    db_client.close()
    db_client = None


app = FastAPI(
    title="Zoo Audio Service",
    description="TTS đa ngôn ngữ — giọng khớp bản dịch, cache MD5, khóa sinh file",
    version="3.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    poi_id: str
    languages: Optional[list[str]] = None


class TextToSpeechRequest(BaseModel):
    text: str
    language: str = "vi"


def require_internal(x_internal_key: Optional[str] = Header(default=None, alias="X-Internal-Key")):
    if x_internal_key != INTERNAL_SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Internal key không hợp lệ")
    return True


def audio_hash(text: str, language: str, voice: str) -> str:
    return hashlib.md5(f"{text}|{language}|{voice}".encode("utf-8")).hexdigest()


def make_audio_filename(text: str, language: str) -> str:
    voice = VOICE_MAP[language]
    return f"{audio_hash(text, language, voice)}.mp3"


def pick_poi_content(poi: dict, language: str):
    """Chỉ đọc đúng bản dịch của language — không đọc tiếng Anh bằng giọng khác."""
    if language not in VOICE_MAP:
        return None
    translations = poi.get("translations") or {}
    tr = translations.get(language) or {}
    description = tr.get("description")
    if not description and language == "vi":
        description = poi.get("description_vi")
    if not description and language == "en":
        description = poi.get("description_en")
    if not description:
        return None
    name = tr.get("name") or poi.get("name") or ""
    return name, description, language, VOICE_MAP[language]


async def get_poi_from_content_service(poi_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{CONTENT_SERVICE_URL}/pois/{poi_id}", timeout=5.0)
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{poi_id}'"},
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail={"error": "content_service_error", "message": "Content Service lỗi"},
                )
            return response.json()
        except HTTPException:
            raise
        except (httpx.ConnectError, httpx.TimeoutException):
            raise HTTPException(
                status_code=503,
                detail={"error": "content_unavailable", "message": "Content Service không phản hồi"},
            )


async def generate_tts_audio(text: str, language: str, output_path: str):
    voice = VOICE_MAP.get(language)
    if not voice:
        raise ValueError(f"Không có giọng cho ngôn ngữ {language}")

    timeout_sec = float(os.getenv("EDGE_TTS_TIMEOUT_SEC", str(EDGE_TTS_TIMEOUT_SEC)))
    backoffs = [0.01, 0.02] if TESTING else [1.0, 3.0]
    max_attempts = len(backoffs) + 1
    last_exc = None

    for attempt in range(max_attempts):
        tmp_path = f"{output_path}.tmp.{uuid.uuid4().hex}"
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await asyncio.wait_for(communicate.save(tmp_path), timeout=timeout_sec)
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                raise RuntimeError("Edge TTS trả về file rỗng")
            os.replace(tmp_path, output_path)
            return
        except Exception as exc:
            last_exc = exc
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            if attempt < len(backoffs):
                log.warning(
                    "Edge TTS thất bại lần %d/%d (%s). Thử lại sau %.1fs: %s",
                    attempt + 1,
                    max_attempts,
                    language,
                    backoffs[attempt],
                    exc,
                )
                await asyncio.sleep(backoffs[attempt])

    log.error("Edge TTS thất bại sau %d lần cho ngôn ngữ %s: %s", max_attempts, language, last_exc)
    raise RuntimeError(f"Edge TTS thất bại sau {max_attempts} lần thử: {last_exc}")


async def _lock_for(key: str) -> asyncio.Lock:
    async with _locks_guard:
        if key not in _locks:
            _locks[key] = asyncio.Lock()
        return _locks[key]


def _db():
    if db_client is None:
        return None
    return db_client[DB_NAME]


async def _save_track(poi_id: str, lang: str, data: dict) -> None:
    _tracks[(poi_id, lang)] = data
    db = _db()
    if db is None:
        return
    await db["audio_tracks"].update_one(
        {"poi_id": poi_id, "lang": lang},
        {"$set": {"poi_id": poi_id, "lang": lang, **data}},
        upsert=True,
    )
    await _report_status_to_content(poi_id, lang, data)


async def _report_status_to_content(poi_id: str, lang: str, data: dict) -> None:
    """
    POI thuộc database của Content Service nên Audio không ghi thẳng `audio_status` nữa,
    mà báo qua API nội bộ. Best-effort: lỗi mạng chỉ ghi log, không làm hỏng việc sinh audio.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.put(
                f"{CONTENT_SERVICE_URL}/internal/pois/{poi_id}/audio-status/{lang}",
                json=data,
                headers={"X-Internal-Key": INTERNAL_SERVICE_KEY},
            )
        if resp.status_code not in (200, 404):  # 404: POI đã bị xóa, bỏ qua
            log.warning("Content Service từ chối audio_status %s/%s: HTTP %s", poi_id, lang, resp.status_code)
    except Exception as exc:
        log.warning("Không báo được audio_status %s/%s cho Content Service: %s", poi_id, lang, exc)


async def _load_track(poi_id: str, lang: str) -> Optional[dict]:
    cached = _tracks.get((poi_id, lang))
    if cached:
        return cached
    db = _db()
    if db is None:
        return None
    doc = await db["audio_tracks"].find_one({"poi_id": poi_id, "lang": lang})
    if doc:
        doc = {k: v for k, v in doc.items() if k != "_id"}
        _tracks[(poi_id, lang)] = doc
    return doc


def _cleanup_old_files(poi_id: str, lang: str, keep_filename: Optional[str] = None) -> None:
    prefix = f"{poi_id}_{lang}_"
    for name in os.listdir(AUDIO_DIR):
        if name.startswith(prefix) and name.endswith(".mp3") and name != keep_filename:
            try:
                os.remove(os.path.join(AUDIO_DIR, name))
            except OSError:
                pass


async def ensure_poi_audio(poi_id: str, language: str, poi: Optional[dict] = None) -> dict:
    if language not in VOICE_MAP:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_language", "message": f"Ngôn ngữ '{language}' không được hỗ trợ. Chọn: {list(VOICE_MAP)}"},
        )
    if poi is None:
        poi = await get_poi_from_content_service(poi_id)
    picked = pick_poi_content(poi, language)
    if not picked:
        raise HTTPException(
            status_code=404,
            detail={"error": "no_translation", "message": f"Chưa có bản dịch {language} cho địa điểm này"},
        )
    name, text, lang, voice = picked
    full_text = f"{name}. {text}" if name else text
    digest = audio_hash(full_text, lang, voice)
    filename = f"{poi_id}_{lang}_{digest}.mp3"
    output_path = os.path.join(AUDIO_DIR, filename)

    lock = await _lock_for(f"{poi_id}:{lang}")
    async with lock:
        # Nếu file đã tồn tại trên đĩa và size > 0: tên file chứa hash nên coi là cache hit ngay
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            existing = await _load_track(poi_id, lang)
            ready = {
                **(existing or {}),
                "status": "ready",
                "hash": digest,
                "filename": filename,
                "voice": voice,
                "cached": True,
                "updated_at": (existing.get("updated_at") if existing else None) or now_utc().isoformat(),
            }
            if not existing or existing.get("hash") != digest or existing.get("status") != "ready":
                await _save_track(poi_id, lang, {k: v for k, v in ready.items() if k != "cached"})
            return ready

        existing = await _load_track(poi_id, lang)
        if existing and existing.get("hash") == digest and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            ready = {
                **existing,
                "status": "ready",
                "filename": filename,
                "cached": True,
                "voice": voice,
            }
            return ready

        await _save_track(
            poi_id,
            lang,
            {
                "status": "generating",
                "hash": digest,
                "filename": filename,
                "voice": voice,
                "updated_at": now_utc().isoformat(),
            },
        )
        try:
            await generate_tts_audio(full_text, lang, output_path)
        except HTTPException:
            await _save_track(
                poi_id,
                lang,
                {
                    "status": "error",
                    "hash": digest,
                    "error": "http",
                    "updated_at": now_utc().isoformat(),
                    "voice": voice,
                },
            )
            raise
        except Exception as exc:
            await _save_track(
                poi_id,
                lang,
                {
                    "status": "error",
                    "hash": digest,
                    "error": str(exc),
                    "updated_at": now_utc().isoformat(),
                    "voice": voice,
                },
            )
            raise HTTPException(
                status_code=502,
                detail={"error": "tts_failed", "message": "Edge TTS gặp lỗi khi tạo audio, vui lòng thử lại sau"},
            )

        _cleanup_old_files(poi_id, lang, keep_filename=filename)
        ready = {
            "status": "ready",
            "hash": digest,
            "filename": filename,
            "voice": voice,
            "cached": False,
            "updated_at": now_utc().isoformat(),
        }
        await _save_track(poi_id, lang, {k: v for k, v in ready.items() if k != "cached"})
        return ready


async def _generate_langs(poi_id: str, languages: Optional[list[str]]) -> None:
    try:
        poi = await get_poi_from_content_service(poi_id)
    except HTTPException:
        log.warning("Warmup/generate bỏ qua %s (không lấy được POI)", poi_id)
        return
    langs = languages or list(VOICE_MAP)
    for lang in langs:
        if not pick_poi_content(poi, lang):
            continue
        try:
            await ensure_poi_audio(poi_id, lang, poi=poi)
        except Exception as exc:
            log.warning("Sinh audio %s/%s lỗi: %s", poi_id, lang, exc)


@app.get("/")
def root():
    return {
        "service": "Audio Service",
        "status": "đang chạy",
        "supported_languages": list(VOICE_MAP.keys()),
        "voices": VOICE_MAP,
        "version": "3.0.0",
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "audio"}


@app.get("/audio/poi/{poi_id}")
async def visitor_poi_audio(
    poi_id: str,
    lang: str = Query("vi"),
    ctx: dict = Depends(require_valid_ticket),
):
    result = await ensure_poi_audio(poi_id, lang)
    path = os.path.join(AUDIO_DIR, result["filename"])
    return FileResponse(path=path, media_type="audio/mpeg", filename=result["filename"])


@app.get("/audio/preview/{poi_id}")
async def admin_preview(
    poi_id: str,
    lang: str = Query("vi"),
    _: dict = Depends(require_roles("admin")),
):
    result = await ensure_poi_audio(poi_id, lang)
    path = os.path.join(AUDIO_DIR, result["filename"])
    return FileResponse(path=path, media_type="audio/mpeg", filename=result["filename"])


@app.get("/audio/status/{poi_id}")
async def audio_status(poi_id: str, _: dict = Depends(require_roles("admin"))):
    statuses = {}
    for lang in VOICE_MAP:
        track = await _load_track(poi_id, lang)
        statuses[lang] = track or {"status": "pending"}
    return {"poi_id": poi_id, "audio_status": statuses}


@app.post("/internal/generate")
async def internal_generate(body: GenerateRequest, _: bool = Depends(require_internal)):
    _spawn(_generate_langs(body.poi_id, body.languages))
    return {"status": "accepted", "poi_id": body.poi_id, "languages": body.languages}


@app.post("/internal/warmup")
async def internal_warmup(_: bool = Depends(require_internal)):
    _spawn(_warmup_all())
    return {"status": "accepted"}


async def _fetch_all_pois(attempts: int = 5, delay: float = 3.0) -> list[dict]:
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{CONTENT_SERVICE_URL}/pois")
                resp.raise_for_status()
                return resp.json().get("pois") or []
        except Exception as exc:
            log.warning("Warmup: lấy danh sách POI lần %s/%s lỗi: %s", attempt + 1, attempts, exc)
            await asyncio.sleep(delay)
    return []


async def _warmup_all():
    """Sinh sẵn audio cho mọi POI × ngôn ngữ, chạy nền; file đã có (cùng hash) thì bỏ qua."""
    pois = await _fetch_all_pois()
    sem = asyncio.Semaphore(3)

    async def _warmup_one(poi_id: str, lang: str, poi: dict):
        if not pick_poi_content(poi, lang):
            return
        async with sem:
            try:
                await ensure_poi_audio(poi_id, lang, poi=poi)
            except Exception as exc:
                log.warning("Warmup sinh audio %s/%s lỗi: %s", poi_id, lang, exc)

    tasks = [
        _warmup_one(poi["id"], lang, poi)
        for poi in pois
        for lang in list(VOICE_MAP)
    ]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@app.delete("/internal/pois/{poi_id}")
async def internal_delete_poi_audio(poi_id: str, _: bool = Depends(require_internal)):
    removed = []
    for name in os.listdir(AUDIO_DIR):
        if name.startswith(f"{poi_id}_") and name.endswith(".mp3"):
            os.remove(os.path.join(AUDIO_DIR, name))
            removed.append(name)
    for key in [k for k in _tracks if k[0] == poi_id]:
        _tracks.pop(key, None)
    db = _db()
    if db is not None:
        # Content Service đã xóa POI (kèm audio_status) trước khi gọi endpoint này, nên chỉ dọn dữ liệu của Audio.
        await db["audio_tracks"].delete_many({"poi_id": poi_id})
    return {"deleted_files": removed}


@app.post("/tts")
async def text_to_speech(request: TextToSpeechRequest, _: dict = Depends(require_roles("admin"))):
    """Công cụ admin: đọc văn bản tùy ý. Du khách dùng GET /audio/poi/{id}."""
    if request.language not in VOICE_MAP:
        raise HTTPException(
            status_code=400,
            detail={"error": "unsupported_language", "message": f"Ngôn ngữ '{request.language}' không được hỗ trợ. Chọn: {list(VOICE_MAP)}"},
        )
    if len(request.text) > 5000:
        raise HTTPException(
            status_code=400,
            detail={"error": "text_too_long", "message": "Text quá dài (tối đa 5000 ký tự)"},
        )
    filename = make_audio_filename(request.text, request.language)
    output_path = os.path.join(AUDIO_DIR, filename)

    lock = await _lock_for(f"tts:{filename}")
    async with lock:
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            try:
                await generate_tts_audio(request.text, request.language, output_path)
            except Exception:
                raise HTTPException(
                    status_code=502,
                    detail={"error": "tts_failed", "message": "Edge TTS gặp lỗi khi tạo audio, vui lòng thử lại sau"},
                )
    file_size = os.path.getsize(output_path) / 1024
    return {
        "message": "Tạo audio thành công!",
        "language": request.language,
        "voice_used": VOICE_MAP[request.language],
        "audio_url": f"/audio/download/{filename}",
        "file_size_kb": round(file_size, 1),
    }


@app.get("/audio/download/{filename}")
async def download_audio(filename: str, _: dict = Depends(require_roles("admin"))):
    if not filename.endswith(".mp3") or os.path.basename(filename) != filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_audio_filename", "message": "Chỉ hỗ trợ file MP3"},
        )
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail={"error": "audio_not_found", "message": "File audio không tồn tại"},
        )
    return FileResponse(path=file_path, media_type="audio/mpeg", filename=filename)


@app.get("/audio/list")
def list_audio_files(_: dict = Depends(require_roles("admin"))):
    files = []
    if os.path.exists(AUDIO_DIR):
        for filename in os.listdir(AUDIO_DIR):
            if filename.endswith(".mp3"):
                file_path = os.path.join(AUDIO_DIR, filename)
                files.append(
                    {
                        "filename": filename,
                        "size_kb": round(os.path.getsize(file_path) / 1024, 1),
                        "download_url": f"/audio/download/{filename}",
                    }
                )
    return {"total_files": len(files), "files": files}