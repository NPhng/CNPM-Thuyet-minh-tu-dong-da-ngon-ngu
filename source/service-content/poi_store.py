"""Lưu trữ POI: MongoDB khi chạy thật, bộ nhớ khi TESTING."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

from pymongo.errors import DuplicateKeyError

CATEGORIES = {
    "thu_an_co",
    "thu_an_thit",
    "linh_truong",
    "chim",
    "bo_sat_luong_cu",
    "tien_ich",
}
LANGS = ("vi", "en", "zh", "ja", "ko")


def seed_poi_path() -> Optional[Path]:
    env = os.getenv("SEED_POI_PATH")
    candidates = []
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent
    candidates.extend(
        [
            here / "seed" / "pois.json",
            here.parent / "seed" / "pois.json",
            Path("/app/seed/pois.json"),
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_seed_pois() -> list[dict]:
    path = seed_poi_path()
    if not path:
        return []
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def public_poi(doc: dict) -> dict:
    if not doc:
        return doc
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


class MemoryPoiStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def list_all(self) -> list[dict]:
        return [deepcopy(d) for d in self.docs.values()]

    async def find(self, poi_id: str) -> Optional[dict]:
        doc = self.docs.get(poi_id)
        return deepcopy(doc) if doc else None

    async def insert(self, doc: dict) -> None:
        if doc["id"] in self.docs:
            raise DuplicateKeyError("duplicate")
        self.docs[doc["id"]] = deepcopy(doc)

    async def replace_fields(self, poi_id: str, fields: dict) -> Optional[dict]:
        if poi_id not in self.docs:
            return None
        self.docs[poi_id].update(deepcopy(fields))
        return deepcopy(self.docs[poi_id])

    async def delete(self, poi_id: str) -> Optional[dict]:
        return self.docs.pop(poi_id, None)

    async def set_audio_status(self, poi_id: str, lang: str, data: dict) -> bool:
        """Audio Service báo trạng thái audio của một ngôn ngữ. False nếu POI không còn."""
        doc = self.docs.get(poi_id)
        if doc is None:
            return False
        doc.setdefault("audio_status", empty_audio_status())[lang] = deepcopy(data)
        return True

    async def seed_if_empty(self) -> int:
        if self.docs:
            return 0
        n = 0
        for raw in load_seed_pois():
            await self.insert(normalize_poi(raw))
            n += 1
        return n


class MongoPoiStore:
    def __init__(self, db):
        self.col = db["pois"]

    async def list_all(self) -> list[dict]:
        return [public_poi(d) async for d in self.col.find({})]

    async def find(self, poi_id: str) -> Optional[dict]:
        doc = await self.col.find_one({"id": poi_id})
        return public_poi(doc) if doc else None

    async def insert(self, doc: dict) -> None:
        await self.col.insert_one(doc)

    async def replace_fields(self, poi_id: str, fields: dict) -> Optional[dict]:
        await self.col.update_one({"id": poi_id}, {"$set": fields})
        return await self.find(poi_id)

    async def delete(self, poi_id: str) -> Optional[dict]:
        doc = await self.find(poi_id)
        if doc:
            await self.col.delete_one({"id": poi_id})
        return doc

    async def set_audio_status(self, poi_id: str, lang: str, data: dict) -> bool:
        """Audio Service báo trạng thái audio của một ngôn ngữ. False nếu POI không còn."""
        res = await self.col.update_one({"id": poi_id}, {"$set": {f"audio_status.{lang}": data}})
        return res.matched_count > 0

    async def seed_if_empty(self) -> int:
        n = 0
        for raw in load_seed_pois():
            poi = normalize_poi(raw)
            existing = await self.col.find_one({"id": poi["id"]})
            if existing:
                continue
            await self.col.insert_one(poi)
            n += 1
        return n


def empty_audio_status() -> dict:
    return {lang: {"status": "pending"} for lang in LANGS}


def normalize_poi(raw: dict) -> dict:
    translations = raw.get("translations") or {}
    vi = translations.get("vi") or {}
    return {
        "id": raw["id"],
        "name": raw.get("name") or vi.get("name") or raw["id"],
        "lat": float(raw.get("lat", raw.get("latitude"))),
        "lon": float(raw.get("lon", raw.get("longitude"))),
        "radius_m": float(raw.get("radius_m", 30)),
        "image_url": raw.get("image_url"),
        "category": raw.get("category") or "tien_ich",
        "species_name": raw.get("species_name"),
        "translations": translations,
        "audio_status": raw.get("audio_status") or empty_audio_status(),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "created_by": raw.get("created_by"),
    }


def changed_translation_langs(old: dict, new_translations: dict) -> list[str]:
    langs = []
    old_tr = old.get("translations") or {}
    for lang in LANGS:
        before = old_tr.get(lang) or {}
        after = (new_translations or {}).get(lang) or {}
        if before.get("name") != after.get("name") or before.get("description") != after.get("description"):
            langs.append(lang)
    return langs