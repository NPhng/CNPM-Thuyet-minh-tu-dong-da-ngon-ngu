"""
Lõi ghi nhận sự kiện (giai đoạn 4) — thuần Python, không phụ thuộc FastAPI/Mongo.

Quy ước thời gian:
- Lưu trong DB: UTC (datetime có tzinfo).
- Hiển thị: giờ Việt Nam (Asia/Ho_Chi_Minh, UTC+7, không có giờ mùa hè).
- "Hôm nay" = ngày theo giờ VN: [00:00:00 VN, 00:00:00 VN ngày hôm sau) — nửa mở,
  nên sự kiện lúc 23:59:59.999999 thuộc hôm nay, lúc 00:00:00 thuộc ngày hôm sau.
"""

from __future__ import annotations

import math
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
EVENT_TYPES = ("listen", "enter", "exit")
DEFAULT_RADIUS_M = 30.0


# ---------------------------------------------------------------- cấu hình

def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(float(os.getenv(name, default))))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    n_active_minutes: int  # N: cửa sổ "đang hoạt động"
    presence_enter_ttl_minutes: int  # enter không có exit chỉ tính "đang ở" tối đa chừng này phút
    dedupe_seconds: int  # cùng (vé, điểm, loại) liên tiếp trong khoảng này = trùng
    geo_tolerance_m: float  # sai số GPS cho phép khi so với radius_m
    rate_limit: int  # số sự kiện tối đa / vé / cửa sổ
    rate_window_sec: int
    require_gps: bool  # true: enter/exit bắt buộc có lat/lon


def load_settings() -> Settings:
    """Đọc env mỗi lần gọi (rẻ) để test đổi được bằng monkeypatch.setenv."""
    n = _env_int("N_ACTIVE_MINUTES", 10, minimum=1)
    ttl = _env_int("PRESENCE_ENTER_TTL_MINUTES", 120, minimum=1)
    return Settings(
        n_active_minutes=n,
        presence_enter_ttl_minutes=max(ttl, n),  # TTL không được ngắn hơn N
        dedupe_seconds=_env_int("EVENT_DEDUPE_SECONDS", 30),
        geo_tolerance_m=_env_float("GEO_TOLERANCE_M", 20.0),
        rate_limit=_env_int("EVENT_RATE_LIMIT", 30, minimum=1),
        rate_window_sec=_env_int("EVENT_RATE_WINDOW_SEC", 60, minimum=1),
        require_gps=_env_bool("EVENT_REQUIRE_GPS", False),
    )


# ---------------------------------------------------------------- thời gian

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """Datetime không có tzinfo (Mongo mặc định) được hiểu là UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_vn_iso(dt: Optional[datetime]) -> Optional[str]:
    """ISO 8601 theo giờ VN, vd 2026-10-23T14:05:00+07:00 (cùng thời điểm với UTC lưu trong DB)."""
    if dt is None:
        return None
    return as_utc(dt).astimezone(VN_TZ).isoformat()


def vn_date_of(dt: datetime) -> date:
    return as_utc(dt).astimezone(VN_TZ).date()


def vn_day_range_utc(day: date) -> tuple[datetime, datetime]:
    """[start, end) của ngày VN `day`, trả về dạng UTC."""
    start = datetime(day.year, day.month, day.day, tzinfo=VN_TZ)
    nxt = day + timedelta(days=1)
    end = datetime(nxt.year, nxt.month, nxt.day, tzinfo=VN_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


# ---------------------------------------------------------------- GPS

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class EventError(Exception):
    """Lỗi nghiệp vụ khi ghi sự kiện; route đổi thành HTTPException."""

    def __init__(self, status: int, code: str, message: str, headers: Optional[dict] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


@dataclass(frozen=True)
class GeoResult:
    distance_m: Optional[float]  # None = không có GPS
    in_zone: Optional[bool]  # None = không có GPS, không kiểm tra được


def check_geo(
    event_type: str,
    poi: dict,
    lat: Optional[float],
    lon: Optional[float],
    settings: Settings,
) -> GeoResult:
    """
    Kiểm tra vị trí so với vùng kích hoạt (radius_m) của POI.
    - in_zone = khoảng cách <= radius_m + sai số GPS.
    - enter: ngoài vùng -> 422 out_of_range.
    - exit : vẫn nằm sâu trong vùng (khoảng cách < radius_m - sai số) -> 422 still_in_range.
    - listen: luôn ghi nhận; ngoài vùng thì đánh dấu in_zone=False (không tính "lượt đi qua").
    - Không có GPS: bỏ qua kiểm tra (in_zone=None), trừ khi require_gps và là enter/exit.
    """
    if lat is None or lon is None:
        if settings.require_gps and event_type in ("enter", "exit"):
            raise EventError(422, "gps_required", "Sự kiện enter/exit cần gửi kèm lat và lon")
        return GeoResult(None, None)

    radius = float(poi.get("radius_m") or DEFAULT_RADIUS_M)
    tol = settings.geo_tolerance_m
    distance = haversine_m(lat, lon, float(poi["lat"]), float(poi["lon"]))
    in_zone = distance <= radius + tol

    if event_type == "enter" and not in_zone:
        raise EventError(
            422,
            "out_of_range",
            f"Cách điểm {distance:.0f} m, vượt vùng kích hoạt {radius:.0f} m (+{tol:.0f} m sai số GPS)",
        )
    if event_type == "exit" and distance < radius - tol:
        raise EventError(
            422,
            "still_in_range",
            f"Còn cách tâm điểm {distance:.0f} m, vẫn trong vùng kích hoạt {radius:.0f} m",
        )
    return GeoResult(round(distance, 1), in_zone)


# ---------------------------------------------------------------- chống trùng / rate limit

def is_duplicate(last: Optional[dict], event_type: str, now: datetime, window_seconds: int) -> bool:
    """
    Trùng = sự kiện gần nhất của cặp (vé, điểm) cùng loại và cách chưa tới `window_seconds`.
    Đúng bằng window thì KHÔNG trùng. So với sự kiện gần nhất (không phải mọi sự kiện cùng loại)
    nên enter -> exit -> enter nhanh vẫn được ghi nhận đủ.
    """
    if not last or window_seconds <= 0 or last.get("type") != event_type:
        return False
    age = (as_utc(now) - as_utc(last["ts"])).total_seconds()
    return 0 <= age < window_seconds


class SlidingWindowLimiter:
    """Giới hạn số lần / khoảng thời gian theo khóa (trong bộ nhớ, 1 tiến trình)."""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window_sec: int, now: datetime) -> Optional[int]:
        """Cho phép -> None (và ghi nhận). Vượt -> số giây nên chờ."""
        t = as_utc(now).timestamp()
        hits = self._hits[key]
        while hits and t - hits[0] >= window_sec:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, math.ceil(window_sec - (t - hits[0])))
        hits.append(t)
        return None

    def prune(self, now: datetime, window_sec: int) -> None:
        t = as_utc(now).timestamp()
        for key in [k for k, h in self._hits.items() if not h or t - h[-1] >= window_sec]:
            del self._hits[key]
