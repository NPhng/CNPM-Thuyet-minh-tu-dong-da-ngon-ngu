"""
Content Service — POI MongoDB, bản dịch 5 ngôn ngữ, kích hoạt TTS nội bộ.
Database riêng: collection `pois`, `events`. Vé lấy từ Auth Service qua HTTP nội bộ (auth_client.py).
Đọc POI (danh sách, chi tiết, nearby) là công khai, không cần vé.
CRUD chỉ admin.
Giai đoạn 4: du khách gửi sự kiện listen/enter/exit (POST /events, cần ticket_token);
admin xem thống kê (/stats/*). Định nghĩa các con số nằm ở đầu file stats.py.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from datetime import date as date_type
from typing import Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, model_validator

import stats
import translator
from audio_client import INTERNAL_SERVICE_KEY, delete_poi_audio, generate_poi_audio, warmup_all_audio
from auth_client import HttpTicketStore
from event_service import EventIngestor, serialize_event
from event_store import MemoryEventStore, MemoryTicketStore, MongoEventStore
from events_core import EventError, load_settings, vn_date_of
from jwt_auth import invalidate_ticket_cache, require_roles, require_valid_ticket, set_ticket_lookup
from poi_store import (
    CATEGORIES,
    LANGS,
    MemoryPoiStore,
    MongoPoiStore,
    changed_translation_langs,
    empty_audio_status,
    normalize_poi,
    public_poi,
)

log = logging.getLogger("content")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27019")
DB_NAME = os.getenv("DB_NAME", "zoo_content")
TESTING = os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
MAX_SEARCH_RADIUS_M = 100000.0

db_client: Optional[AsyncIOMotorClient] = None
store = MemoryPoiStore()
event_store = MemoryEventStore()
ticket_store = MemoryTicketStore()
ingestor: Optional[EventIngestor] = None


def get_store():
    return store


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_internal(x_internal_key: Optional[str] = Header(default=None, alias="X-Internal-Key")):
    if x_internal_key != INTERNAL_SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Internal key không hợp lệ")
    return True


def _make_ingestor() -> EventIngestor:
    # lambda để luôn dùng now_utc hiện tại của module (test có thể thay bằng đồng hồ giả)
    return EventIngestor(event_store, clock=lambda: now_utc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, store, event_store, ticket_store, ingestor
    invalidate_ticket_cache()
    if TESTING:
        store = MemoryPoiStore()
        await store.seed_if_empty()
        event_store = MemoryEventStore()
        ticket_store = MemoryTicketStore()
        set_ticket_lookup(lambda ticket_id: ticket_store.find(ticket_id))
        ingestor = _make_ingestor()
        yield
        return

    # tz_aware: đọc datetime từ Mongo ra có tzinfo=UTC (không bị hiểu nhầm giờ địa phương)
    db_client = AsyncIOMotorClient(MONGO_URI, tz_aware=True)
    db = db_client[DB_NAME]
    await db["pois"].create_index("id", unique=True)
    await db["pois"].create_index("category")
    store = MongoPoiStore(db)
    event_store = MongoEventStore(db)
    ticket_store = HttpTicketStore()  # vé thuộc database của Auth Service
    await event_store.ensure_indexes()
    set_ticket_lookup(lambda ticket_id: ticket_store.find(ticket_id))
    ingestor = _make_ingestor()
    inserted = await store.seed_if_empty()
    log.info("Seed POI mới: %s", inserted)
    asyncio.create_task(_warmup_audio_later())
    yield
    db_client.close()
    db_client = None


async def _warmup_audio_later():
    """Chạy nền, không chặn khởi động. Thử lại vài lần nếu Audio Service chưa sẵn sàng."""
    for attempt in range(5):
        await asyncio.sleep(3 * (attempt + 1))
        if await warmup_all_audio():
            return
    log.warning("Warmup audio không thành công sau 5 lần; audio sẽ sinh khi có request.")


app = FastAPI(
    title="Zoo Content Service",
    description="POI Thảo Cầm Viên — MongoDB, bản dịch, kích hoạt audio",
    version="4.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Translation(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class POICreate(BaseModel):
    name: Optional[str] = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(30.0, gt=0, description="Vùng kích hoạt của điểm (khác search_radius_m khi tìm kiếm)")
    image_url: Optional[str] = None
    category: str
    species_name: Optional[str] = None
    translations: dict[str, Translation]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Khu Demo",
                    "lat": 10.79,
                    "lon": 106.71,
                    "radius_m": 20,
                    "category": "tien_ich",
                    "translations": {
                        "vi": {"name": "Khu Demo", "description": "Mô tả tiếng Việt hai câu. Câu hai."},
                        "en": {"name": "Demo Zone", "description": "English description. Second sentence."},
                    },
                }
            ]
        }
    }


class POIUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    radius_m: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    category: Optional[str] = None
    species_name: Optional[str] = None
    translations: Optional[dict[str, Translation]] = None


class TranslationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, min_length=1)


class TranslateRequest(BaseModel):
    name: str
    description: str


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def visitor_poi(doc: dict) -> dict:
    """Bản công khai cho du khách: không lộ audio_status (tên file, lỗi nội bộ)."""
    return {k: v for k, v in public_poi(doc).items() if k != "audio_status"}


def _mark_audio_pending(poi: dict, langs: list[str]) -> dict:
    status = dict(poi.get("audio_status") or empty_audio_status())
    for lang in langs:
        status[lang] = {"status": "pending"}
    return status


def _validate_category(category: str) -> None:
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category không hợp lệ. Chọn: {sorted(CATEGORIES)}")


def _translations_dump(translations: dict) -> dict:
    out = {}
    for lang, item in translations.items():
        if lang not in LANGS:
            raise HTTPException(status_code=400, detail=f"Ngôn ngữ không hỗ trợ: {lang}")
        data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
        out[lang] = data
    return out


def _nearby_payload(pois: list[dict], lat: float, lon: float, search_radius_m: float) -> dict:
    nearby = []
    for poi in pois:
        try:
            plat = float(poi.get("lat"))
            plon = float(poi.get("lon"))
            if math.isnan(plat) or math.isnan(plon) or math.isinf(plat) or math.isinf(plon):
                continue
            if not (-90 <= plat <= 90 and -180 <= plon <= 180):
                continue
            rad_raw = poi.get("radius_m")
            if rad_raw is None:
                rad = 30.0
            else:
                rad = float(rad_raw)
                if math.isnan(rad) or math.isinf(rad) or rad <= 0:
                    log.warning("Bỏ qua POI %s do radius_m không hợp lệ: %s", poi.get("id"), rad_raw)
                    continue
        except (TypeError, ValueError):
            log.warning("Bỏ qua POI %s do toạ độ/bán kính hỏng", poi.get("id"))
            continue

        distance = calculate_distance(lat, lon, plat, plon)
        if distance <= search_radius_m:
            nearby.append(
                {
                    **visitor_poi(poi),
                    "distance_m": round(distance, 1),
                    "within_poi_radius": distance <= rad,
                }
            )
    nearby.sort(key=lambda x: x["distance_m"])
    return {
        "search_location": {"lat": lat, "lon": lon},
        "search_radius_m": search_radius_m,
        "found": len(nearby),
        "pois": nearby,
        "note": "search_radius_m là bán kính tìm kiếm GPS; radius_m là vùng kích hoạt của từng POI.",
    }


@app.get("/")
async def root():
    pois = await get_store().list_all()
    return {
        "service": "Content Service",
        "status": "đang chạy",
        "total_pois": len(pois),
        "version": "4.0.0",
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "content"}


@app.get("/pois")
async def get_all_pois(category: Optional[str] = None):
    pois = await get_store().list_all()
    if category:
        pois = [p for p in pois if p.get("category") == category]
    return {"total": len(pois), "pois": [visitor_poi(p) for p in pois]}


@app.get("/pois/nearby")
async def search_nearby_pois(
    lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    lon: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    search_radius_m: float = Query(
        50.0,
        gt=0,
        le=MAX_SEARCH_RADIUS_M,
        allow_inf_nan=False,
        description="Bán kính tìm kiếm GPS, khác radius_m của POI",
    ),
):
    pois = await get_store().list_all()
    return _nearby_payload(pois, lat, lon, search_radius_m)


@app.get("/pois/nearby/search")
async def search_nearby_pois_alias(
    lat: float = Query(..., ge=-90, le=90, allow_inf_nan=False),
    lon: float = Query(..., ge=-180, le=180, allow_inf_nan=False),
    radius_m: float = Query(50.0, gt=0, le=MAX_SEARCH_RADIUS_M, allow_inf_nan=False),
):
    """Alias cũ: radius_m ở đây là search_radius_m."""
    pois = await get_store().list_all()
    return _nearby_payload(pois, lat, lon, radius_m)


@app.get("/pois/{poi_id}")
async def get_poi(poi_id: str):
    poi = await get_store().find(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm với ID '{poi_id}'"},
        )
    return visitor_poi(poi)


@app.get("/pois/{poi_id}/audio-status")
async def get_poi_audio_status(poi_id: str, _: dict = Depends(require_roles("admin"))):
    """Admin: trạng thái audio từng ngôn ngữ (pending / generating / ready / error)."""
    poi = await get_store().find(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{poi_id}'"},
        )
    return {"poi_id": poi_id, "audio_status": poi.get("audio_status") or empty_audio_status()}


@app.put("/internal/pois/{poi_id}/audio-status/{lang}")
async def internal_set_audio_status(poi_id: str, lang: str, body: dict, _: bool = Depends(require_internal)):
    """Audio Service báo trạng thái sinh audio (generating / ready / error) để admin xem trong POI."""
    if lang not in LANGS:
        raise HTTPException(status_code=400, detail=f"Ngôn ngữ không hỗ trợ. Chọn: {list(LANGS)}")
    if not await get_store().set_audio_status(poi_id, lang, body):
        raise HTTPException(status_code=404, detail=f"Không tìm thấy địa điểm '{poi_id}'")
    return {"poi_id": poi_id, "lang": lang}


@app.post("/pois", status_code=201)
async def create_poi(
    poi_data: POICreate,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_roles("admin")),
):
    _validate_category(poi_data.category)
    translations = _translations_dump(poi_data.translations)
    if "vi" not in translations:
        raise HTTPException(status_code=400, detail="Cần bản dịch vi (name + description)")
    new_id = f"tcv-{uuid.uuid4().hex[:8]}"
    new_poi = normalize_poi(
        {
            "id": new_id,
            "name": poi_data.name or translations["vi"]["name"],
            "lat": poi_data.lat,
            "lon": poi_data.lon,
            "radius_m": poi_data.radius_m,
            "image_url": poi_data.image_url,
            "category": poi_data.category,
            "species_name": poi_data.species_name,
            "translations": translations,
            "audio_status": empty_audio_status(),
            "created_by": payload.get("username", "unknown"),
            "created_at": now_utc().isoformat(),
        }
    )
    await get_store().insert(new_poi)
    langs = [lang for lang in LANGS if translations.get(lang, {}).get("description")]
    background_tasks.add_task(generate_poi_audio, new_id, langs)
    return {"message": "Thêm địa điểm thành công!", "poi": public_poi(new_poi)}


@app.post("/translate")
async def translate_poi(
    body: TranslateRequest,
    _: dict = Depends(require_roles("admin")),
):
    name = (body.name or "").strip()
    desc = (body.description or "").strip()
    if not name or not desc:
        raise HTTPException(status_code=400, detail="Tên và mô tả tiếng Việt không được để trống")
    if len(name) > 200:
        raise HTTPException(status_code=400, detail="Tên không được vượt quá 200 ký tự")
    if len(desc) > 4500:
        raise HTTPException(status_code=400, detail="Mô tả không được vượt quá 4500 ký tự")

    async def _do_translations():
        tasks = [
            asyncio.to_thread(translator.translate_text, name, "en"),
            asyncio.to_thread(translator.translate_text, desc, "en"),
            asyncio.to_thread(translator.translate_text, name, "zh"),
            asyncio.to_thread(translator.translate_text, desc, "zh"),
            asyncio.to_thread(translator.translate_text, name, "ja"),
            asyncio.to_thread(translator.translate_text, desc, "ja"),
            asyncio.to_thread(translator.translate_text, name, "ko"),
            asyncio.to_thread(translator.translate_text, desc, "ko"),
        ]
        res = await asyncio.gather(*tasks)
        return {
            "translations": {
                "en": {"name": res[0], "description": res[1]},
                "zh": {"name": res[2], "description": res[3]},
                "ja": {"name": res[4], "description": res[5]},
                "ko": {"name": res[6], "description": res[7]},
            }
        }

    try:
        return await asyncio.wait_for(_do_translations(), timeout=25)
    except Exception as exc:
        log.exception("Lỗi khi dịch ngôn ngữ: %s", exc)
        raise HTTPException(status_code=502, detail="Không dịch được, vui lòng thử lại sau")


@app.put("/pois/{poi_id}")
async def update_poi(
    poi_id: str,
    poi_data: POIUpdate,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_roles("admin")),
):
    poi = await get_store().find(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{poi_id}'"},
        )
    changes = poi_data.model_dump(exclude_none=True)
    regen_langs: list[str] = []
    if "category" in changes:
        _validate_category(changes["category"])
    if "translations" in changes:
        new_tr = _translations_dump(changes["translations"])
        merged = {**(poi.get("translations") or {}), **new_tr}
        regen_langs = changed_translation_langs(poi, merged)
        changes["translations"] = merged
        if regen_langs:
            changes["audio_status"] = _mark_audio_pending(poi, regen_langs)
        if "vi" in merged:
            changes["name"] = changes.get("name") or merged["vi"].get("name") or poi.get("name")
    changes["updated_at"] = now_utc().isoformat()
    changes["updated_by"] = payload.get("username")
    updated = await get_store().replace_fields(poi_id, changes)
    if regen_langs:
        background_tasks.add_task(generate_poi_audio, poi_id, regen_langs)
    return {"message": "Cập nhật địa điểm thành công!", "poi": public_poi(updated)}


@app.patch("/pois/{poi_id}/translations/{lang}")
async def patch_translation(
    poi_id: str,
    lang: str,
    body: TranslationUpdate,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_roles("admin")),
):
    if lang not in LANGS:
        raise HTTPException(status_code=400, detail=f"Ngôn ngữ không hỗ trợ. Chọn: {list(LANGS)}")
    poi = await get_store().find(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{poi_id}'"},
        )
    translations = dict(poi.get("translations") or {})
    current = dict(translations.get(lang) or {})
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Không có trường nào để sửa")
    current.update(patch)
    if not current.get("name") or not current.get("description"):
        raise HTTPException(status_code=400, detail="Bản dịch cần name và description")
    translations[lang] = current
    fields = {
        "translations": translations,
        "audio_status": _mark_audio_pending(poi, [lang]),
        "updated_at": now_utc().isoformat(),
        "updated_by": payload.get("username"),
    }
    if lang == "vi":
        fields["name"] = current["name"]
    if changed_translation_langs(poi, translations):
        updated = await get_store().replace_fields(poi_id, fields)
        background_tasks.add_task(generate_poi_audio, poi_id, [lang])
    else:
        fields.pop("audio_status")
        updated = await get_store().replace_fields(poi_id, fields)
    return {"message": f"Đã cập nhật bản dịch {lang}", "poi": public_poi(updated)}


@app.delete("/pois/{poi_id}")
async def delete_poi(
    poi_id: str,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(require_roles("admin")),
):
    deleted = await get_store().delete(poi_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{poi_id}'"},
        )
    background_tasks.add_task(delete_poi_audio, poi_id)
    return {
        "message": f"Đã xóa địa điểm '{deleted.get('name')}' thành công",
        "deleted_poi_id": poi_id,
    }


# ======================================================================
# Giai đoạn 4 — ghi nhận sự kiện và thống kê
# ======================================================================

class EventCreate(BaseModel):
    poi_id: str = Field(min_length=1, max_length=64)
    type: Literal["listen", "enter", "exit"]
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Vị trí GPS hiện tại (tùy chọn; có thì server kiểm tra Haversine)")
    lon: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def _lat_lon_together(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError("Cần gửi cả lat và lon, hoặc không gửi cả hai")
        return self

    model_config = {
        "json_schema_extra": {"examples": [{"poi_id": "tcv-001", "type": "enter", "lat": 10.78755, "lon": 106.70528}]}
    }


def _event_http_error(exc: EventError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"error": exc.code, "message": exc.message},
        headers=exc.headers or None,
    )


@app.post("/events", status_code=201)
async def post_event(body: EventCreate, response: Response, ctx: dict = Depends(require_valid_ticket)):
    """
    Du khách (ticket_token) gửi listen / enter / exit.
    - 201: đã ghi. 200 + `deduplicated: true`: trùng sự kiện ngay trước đó (không ghi thêm).
    - 404: POI không tồn tại. 422: enter ngoài vùng / exit còn sâu trong vùng (khi có GPS).
    - 429: gửi quá nhanh. `ts` do server đặt, trả về theo giờ VN.
    """
    ticket_id = ctx["ticket"].get("id") or ctx["payload"].get("ticket_id")
    try:
        ingestor.check_rate(ticket_id)
        poi = await get_store().find(body.poi_id)
        if not poi:
            raise HTTPException(status_code=404, detail={"error": "poi_not_found", "message": f"Không tìm thấy địa điểm '{body.poi_id}'"})
        event, duplicate = await ingestor.record(
            ticket_id=ticket_id, poi=poi, event_type=body.type, lat=body.lat, lon=body.lon
        )
    except EventError as exc:
        raise _event_http_error(exc)
    if duplicate:
        response.status_code = 200
    return {"event": serialize_event(event), "deduplicated": duplicate}


@app.get("/events")
async def list_events(
    poi_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    _: dict = Depends(require_roles("admin")),
):
    """Admin: sự kiện mới nhất trước (kiểm tra dữ liệu, xem hoạt động gần đây)."""
    docs = await event_store.recent(poi_id=poi_id, ticket_id=ticket_id, limit=limit)
    return {"total": len(docs), "events": [serialize_event(d) for d in docs]}


@app.get("/stats/overview")
async def stats_overview(_: dict = Depends(require_roles("admin"))):
    """Vé bán hôm nay + số vé đang hoạt động (có sự kiện trong N_ACTIVE_MINUTES phút gần nhất)."""
    return await stats.build_overview(event_store, ticket_store, now_utc(), load_settings())


@app.get("/stats/pois")
async def stats_pois(_: dict = Depends(require_roles("admin"))):
    """Từng điểm: số người đang ở trong điểm và lượt đi qua hôm nay."""
    pois = await get_store().list_all()
    return await stats.build_pois(event_store, pois, now_utc(), load_settings())


@app.get("/stats/hourly")
async def stats_hourly(
    day: Optional[date_type] = Query(None, alias="date", description="YYYY-MM-DD theo giờ VN; mặc định hôm nay"),
    _: dict = Depends(require_roles("admin")),
):
    """Chuỗi 24 giờ trong ngày (giờ VN) để vẽ biểu đồ."""
    target = day or vn_date_of(now_utc())
    return await stats.build_hourly(event_store, ticket_store, target)


@app.get("/stats/dashboard")
async def stats_dashboard(_: dict = Depends(require_roles("admin"))):
    """Gộp overview + pois + hourly (hôm nay) trong một lần gọi cho dashboard."""
    pois = await get_store().list_all()
    return await stats.build_dashboard(event_store, ticket_store, pois, now_utc(), load_settings())