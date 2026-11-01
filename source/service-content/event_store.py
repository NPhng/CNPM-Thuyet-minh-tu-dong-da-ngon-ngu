"""
Lưu trữ events (ghi) và tickets (chỉ đọc, do Auth Service ghi) — Mongo khi chạy thật, bộ nhớ khi TESTING.

Không import pymongo/motor ở mức module để phần logic và test chạy được mà không cần cài driver.
Mọi `ts` / `created_at` trả ra đều là datetime UTC có tzinfo.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Optional

from events_core import as_utc

_EVENT_PROJECTION = {"_id": 0, "id": 1, "ticket_id": 1, "poi_id": 1, "type": 1, "ts": 1, "distance_m": 1, "in_zone": 1}


def _normalize_event(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["ts"] = as_utc(out["ts"])
    return out


class MemoryEventStore:
    def __init__(self):
        self.docs: list[dict] = []

    async def ensure_indexes(self) -> None:
        return None

    async def insert(self, doc: dict) -> None:
        self.docs.append(deepcopy(doc))

    async def insert_many(self, docs: list[dict]) -> None:
        self.docs.extend(deepcopy(d) for d in docs)

    async def last_for(self, ticket_id: str, poi_id: str) -> Optional[dict]:
        """Sự kiện mới nhất của cặp (vé, điểm); cùng ts thì lấy cái ghi sau."""
        best = None
        for d in self.docs:
            if d["ticket_id"] == ticket_id and d["poi_id"] == poi_id:
                if best is None or as_utc(d["ts"]) >= as_utc(best["ts"]):
                    best = d
        return _normalize_event(best) if best else None

    async def find_range(self, start: datetime, end: datetime, end_inclusive: bool = False) -> list[dict]:
        """Sự kiện có start <= ts < end (hoặc <= end), sắp xếp ts tăng dần."""
        start, end = as_utc(start), as_utc(end)
        hits = [
            d
            for d in self.docs
            if as_utc(d["ts"]) >= start and (as_utc(d["ts"]) <= end if end_inclusive else as_utc(d["ts"]) < end)
        ]
        hits.sort(key=lambda d: as_utc(d["ts"]))  # sort ổn định: cùng ts giữ thứ tự ghi
        return [_normalize_event(d) for d in hits]

    async def recent(self, poi_id: Optional[str] = None, ticket_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        hits = [
            d
            for d in self.docs
            if (poi_id is None or d["poi_id"] == poi_id) and (ticket_id is None or d["ticket_id"] == ticket_id)
        ]
        hits.sort(key=lambda d: as_utc(d["ts"]), reverse=True)
        return [_normalize_event(d) for d in hits[:limit]]

    async def delete_demo(self) -> int:
        before = len(self.docs)
        self.docs = [d for d in self.docs if not d.get("demo")]
        return before - len(self.docs)


class MongoEventStore:
    """Collection `events`. Index: (ts), (poi_id, ts), (ticket_id, ts)."""

    def __init__(self, db):
        self.col = db["events"]

    async def ensure_indexes(self) -> None:
        await self.col.create_index([("ts", 1)])
        await self.col.create_index([("poi_id", 1), ("ts", 1)])
        await self.col.create_index([("ticket_id", 1), ("ts", 1)])

    async def insert(self, doc: dict) -> None:
        await self.col.insert_one(dict(doc))

    async def insert_many(self, docs: list[dict]) -> None:
        if docs:
            await self.col.insert_many([dict(d) for d in docs])

    async def last_for(self, ticket_id: str, poi_id: str) -> Optional[dict]:
        cursor = self.col.find({"ticket_id": ticket_id, "poi_id": poi_id}, _EVENT_PROJECTION).sort(
            [("ts", -1), ("_id", -1)]
        ).limit(1)
        docs = await cursor.to_list(length=1)
        return _normalize_event(docs[0]) if docs else None

    async def find_range(self, start: datetime, end: datetime, end_inclusive: bool = False) -> list[dict]:
        upper = "$lte" if end_inclusive else "$lt"
        cursor = self.col.find({"ts": {"$gte": as_utc(start), upper: as_utc(end)}}, _EVENT_PROJECTION).sort(
            [("ts", 1), ("_id", 1)]
        )
        return [_normalize_event(d) for d in await cursor.to_list(length=None)]

    async def recent(self, poi_id: Optional[str] = None, ticket_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        query: dict = {}
        if poi_id is not None:
            query["poi_id"] = poi_id
        if ticket_id is not None:
            query["ticket_id"] = ticket_id
        cursor = self.col.find(query, _EVENT_PROJECTION).sort([("ts", -1), ("_id", -1)]).limit(limit)
        return [_normalize_event(d) for d in await cursor.to_list(length=limit)]

    async def delete_demo(self) -> int:
        res = await self.col.delete_many({"demo": True})
        return res.deleted_count


class MemoryTicketStore:
    """Vé (bộ nhớ, dùng khi TESTING). Auth Service mới là nơi tạo vé thật."""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    def add(self, doc: dict) -> None:
        self.docs[doc["id"]] = deepcopy(doc)

    async def find(self, ticket_id: str) -> Optional[dict]:
        doc = self.docs.get(ticket_id)
        return deepcopy(doc) if doc else None

    async def insert_many(self, docs: list[dict]) -> None:
        for d in docs:
            self.add(d)

    async def created_between(self, start: datetime, end: datetime) -> list[dict]:
        """Vé có start <= created_at < end -> [{id, created_at(UTC)}]."""
        start, end = as_utc(start), as_utc(end)
        return [
            {"id": d["id"], "created_at": as_utc(d["created_at"])}
            for d in self.docs.values()
            if d.get("created_at") is not None and start <= as_utc(d["created_at"]) < end
        ]

    async def delete_demo(self) -> int:
        ids = [i for i, d in self.docs.items() if d.get("demo")]
        for i in ids:
            del self.docs[i]
        return len(ids)


class MongoTicketStore:
    """Đọc collection `tickets` do Auth Service quản lý (cùng database)."""

    def __init__(self, db):
        self.col = db["tickets"]

    async def find(self, ticket_id: str) -> Optional[dict]:
        return await self.col.find_one({"id": ticket_id})

    async def insert_many(self, docs: list[dict]) -> None:
        if docs:
            await self.col.insert_many([dict(d) for d in docs])

    async def created_between(self, start: datetime, end: datetime) -> list[dict]:
        cursor = self.col.find(
            {"created_at": {"$gte": as_utc(start), "$lt": as_utc(end)}},
            {"_id": 0, "id": 1, "created_at": 1},
        )
        docs = await cursor.to_list(length=None)
        return [{"id": d.get("id"), "created_at": as_utc(d["created_at"])} for d in docs]

    async def delete_demo(self) -> int:
        res = await self.col.delete_many({"demo": True})
        return res.deleted_count
