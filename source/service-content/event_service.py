"""Ghi sự kiện du khách: rate limit -> kiểm tra GPS -> chống trùng -> lưu."""

from __future__ import annotations

import asyncio
import uuid
import zlib
from datetime import datetime
from typing import Callable, Optional

from events_core import (
    EventError,
    Settings,
    SlidingWindowLimiter,
    check_geo,
    is_duplicate,
    load_settings,
    now_utc,
    to_vn_iso,
)

_LOCK_STRIPES = 64


def serialize_event(doc: dict) -> dict:
    """Dạng trả ra API: `ts` theo giờ VN (+07:00)."""
    return {
        "id": doc.get("id"),
        "ticket_id": doc["ticket_id"],
        "poi_id": doc["poi_id"],
        "type": doc["type"],
        "ts": to_vn_iso(doc["ts"]),
        "distance_m": doc.get("distance_m"),
        "in_zone": doc.get("in_zone"),
    }


class EventIngestor:
    """
    Tạo mới cho mỗi lần khởi động app (khóa asyncio gắn với event loop của lần chạy đó).

    Chống gửi trùng: kiểm tra-rồi-ghi được bảo vệ bằng khóa theo (vé, điểm) trong 1 tiến trình
    (uvicorn 1 worker như Dockerfile hiện tại). Chạy nhiều worker/instance thì cần thêm khóa ở tầng DB.
    """

    def __init__(
        self,
        store,
        clock: Callable[[], datetime] = now_utc,
        settings_fn: Callable[[], Settings] = load_settings,
    ):
        self.store = store
        self.clock = clock
        self.settings_fn = settings_fn
        self.limiter = SlidingWindowLimiter()
        self._locks = [asyncio.Lock() for _ in range(_LOCK_STRIPES)]
        self._calls = 0

    def _lock_for(self, ticket_id: str, poi_id: str) -> asyncio.Lock:
        return self._locks[zlib.crc32(f"{ticket_id}|{poi_id}".encode()) % _LOCK_STRIPES]

    def check_rate(self, ticket_id: str) -> None:
        """Giới hạn số sự kiện / vé / cửa sổ; mọi lần gửi (kể cả trùng) đều tính."""
        s = self.settings_fn()
        now = self.clock()
        self._calls += 1
        if self._calls % 500 == 0:
            self.limiter.prune(now, s.rate_window_sec)
        wait = self.limiter.check(ticket_id, s.rate_limit, s.rate_window_sec, now)
        if wait is not None:
            raise EventError(
                429,
                "rate_limited",
                "Gửi sự kiện quá nhanh, vui lòng thử lại sau",
                headers={"Retry-After": str(wait)},
            )

    async def record(
        self,
        *,
        ticket_id: str,
        poi: dict,
        event_type: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> tuple[dict, bool]:
        """
        Trả (event, deduplicated). `ts` luôn là giờ máy chủ (không tin giờ do app gửi).
        Tọa độ thô không được lưu, chỉ lưu distance_m và in_zone.
        """
        s = self.settings_fn()
        geo = check_geo(event_type, poi, lat, lon, s)
        async with self._lock_for(ticket_id, poi["id"]):
            now = self.clock()
            last = await self.store.last_for(ticket_id, poi["id"])
            if is_duplicate(last, event_type, now, s.dedupe_seconds):
                return last, True
            doc = {
                "id": str(uuid.uuid4()),
                "ticket_id": ticket_id,
                "poi_id": poi["id"],
                "type": event_type,
                "ts": now,
                "distance_m": geo.distance_m,
                "in_zone": geo.in_zone,
            }
            await self.store.insert(doc)
            return doc, False
