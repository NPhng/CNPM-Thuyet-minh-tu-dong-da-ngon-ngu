"""
Gọi Auth Service nội bộ (X-Internal-Key) để lấy dữ liệu vé.

Content Service có database riêng, KHÔNG đọc thẳng collection `tickets` của Auth Service nữa.
`HttpTicketStore` có cùng giao diện với MemoryTicketStore (find / created_between / insert_many / delete_demo)
nên stats.py, jwt_auth và seed_demo.py dùng lại được mà không phải sửa logic.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from events_core import as_utc

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001").rstrip("/")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "").strip()  # đã được audio_client kiểm tra độ mạnh khi khởi động
_TIMEOUT = 5.0


def _headers() -> dict:
    return {"X-Internal-Key": INTERNAL_SERVICE_KEY}


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail="Auth Service không phản hồi")


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    return as_utc(value).isoformat() if isinstance(value, datetime) else str(value)


class HttpTicketStore:
    """Vé nằm trong database của Auth Service; truy cập qua HTTP."""

    async def find(self, ticket_id: str) -> Optional[dict]:
        url = f"{AUTH_SERVICE_URL}/internal/tickets/{quote(str(ticket_id), safe='')}"
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, headers=_headers())
        except httpx.HTTPError:
            raise _unavailable()
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Auth Service lỗi")
        return resp.json()

    async def created_between(self, start: datetime, end: datetime) -> list[dict]:
        """Vé có start <= created_at < end -> [{id, created_at(UTC)}]."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{AUTH_SERVICE_URL}/internal/tickets/created-between",
                    params={"start": _iso(start), "end": _iso(end)},
                    headers=_headers(),
                )
        except httpx.HTTPError:
            raise _unavailable()
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Auth Service lỗi")
        return [
            {"id": t.get("id"), "created_at": as_utc(datetime.fromisoformat(t["created_at"]))}
            for t in resp.json().get("tickets", [])
        ]

    async def insert_many(self, docs: list[dict]) -> None:
        """Nạp vé demo vào database của Auth Service (dùng cho seed_demo.py)."""
        if not docs:
            return
        payload = {
            "tickets": [
                {
                    **{k: v for k, v in d.items() if k not in {"created_at", "expires_at", "activated_at"}},
                    "created_at": _iso(d.get("created_at")),
                    "expires_at": _iso(d.get("expires_at")),
                    "activated_at": _iso(d.get("activated_at")),
                }
                for d in docs
            ]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{AUTH_SERVICE_URL}/internal/tickets/demo", json=payload, headers=_headers())
        resp.raise_for_status()

    async def delete_demo(self) -> int:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.delete(f"{AUTH_SERVICE_URL}/internal/tickets/demo", headers=_headers())
        resp.raise_for_status()
        return int(resp.json().get("deleted", 0))
