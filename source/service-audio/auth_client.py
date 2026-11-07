"""
Tra vé qua Auth Service (X-Internal-Key) — Audio Service có database riêng,
KHÔNG đọc thẳng collection `tickets` của Auth Service.

Dùng làm hàm lookup cho jwt_auth.set_ticket_lookup (kết quả được cache ngắn trong jwt_auth).
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001").rstrip("/")
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "").strip()  # main.py đã kiểm tra độ mạnh khi khởi động


async def fetch_ticket(ticket_id: str) -> Optional[dict]:
    url = f"{AUTH_SERVICE_URL}/internal/tickets/{quote(str(ticket_id), safe='')}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers={"X-Internal-Key": INTERNAL_SERVICE_KEY})
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Auth Service không phản hồi")
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Auth Service lỗi")
    return resp.json()
