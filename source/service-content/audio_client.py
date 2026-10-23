"""Gọi Audio Service nội bộ (service key), không chặn request người dùng."""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("content.audio")

AUDIO_SERVICE_URL = os.getenv("AUDIO_SERVICE_URL", "http://audio-service:8003").rstrip("/")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "internal-secret-change-me")
TESTING = os.getenv("TESTING", "").lower() in {"1", "true", "yes"}


async def generate_poi_audio(poi_id: str, languages: list[str] | None = None) -> None:
    if TESTING or not languages:
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(
                f"{AUDIO_SERVICE_URL}/internal/generate",
                json={"poi_id": poi_id, "languages": languages},
                headers={"X-Internal-Key": INTERNAL_SERVICE_KEY},
            )
    except Exception as exc:
        log.warning("Không gọi được Audio Service để sinh %s: %s", poi_id, exc)


async def delete_poi_audio(poi_id: str) -> None:
    if TESTING:
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.delete(
                f"{AUDIO_SERVICE_URL}/internal/pois/{poi_id}",
                headers={"X-Internal-Key": INTERNAL_SERVICE_KEY},
            )
    except Exception as exc:
        log.warning("Không dọn được audio %s: %s", poi_id, exc)


async def warmup_all_audio() -> bool:
    """Yêu cầu Audio Service sinh sẵn toàn bộ audio. Trả True nếu được chấp nhận."""
    if TESTING:
        return True
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{AUDIO_SERVICE_URL}/internal/warmup",
                headers={"X-Internal-Key": INTERNAL_SERVICE_KEY},
            )
            return resp.status_code == 200
    except Exception as exc:
        log.warning("Warmup audio thất bại: %s", exc)
        return False
