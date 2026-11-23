"""Quản lý vé: tạo, danh sách hôm nay, kích hoạt, đổi máy."""

from __future__ import annotations

import logging
import os
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Optional
from zoneinfo import ZoneInfo

import jwt
import uuid
from fastapi import HTTPException, Request

from jwt_auth import JWT_ALGORITHM, JWT_SECRET, invalidate_ticket_cache

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost").rstrip("/")
TICKET_TTL = os.getenv("TICKET_TTL", "end_of_day")
ACTIVATED_TICKET_TTL_SECONDS = int(os.getenv("ACTIVATED_TICKET_TTL_SECONDS", "60"))
ACTIVATE_RATE_LIMIT = int(os.getenv("ACTIVATE_RATE_LIMIT", "20"))
ACTIVATE_IP_RATE_LIMIT = int(os.getenv("ACTIVATE_IP_RATE_LIMIT", "300"))
ACTIVATE_RATE_WINDOW_SEC = int(os.getenv("ACTIVATE_RATE_WINDOW_SEC", "60"))

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_rate_lock = Lock()
_rate_hits: dict[str, deque] = defaultdict(deque)


def now_vn() -> datetime:
    return datetime.now(VN_TZ)


def to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def compute_expires_at(created_at: datetime) -> datetime:
    """
    TICKET_TTL=end_of_day → 23:59:59 giờ VN ngày mua.
    TICKET_TTL=24h / 8h / 3600s → cộng khoảng thời gian.
    """
    local = created_at.astimezone(VN_TZ) if created_at.tzinfo else created_at.replace(tzinfo=VN_TZ)
    ttl = (TICKET_TTL or "end_of_day").strip().lower()
    if ttl in {"end_of_day", "eod", "same_day"}:
        return local.replace(hour=23, minute=59, second=59, microsecond=0)
    seconds = None
    try:
        if ttl.endswith("h"):
            seconds = int(float(ttl[:-1]) * 3600)
        elif ttl.endswith("s"):
            seconds = int(float(ttl[:-1]))
        elif ttl.isdigit():
            seconds = int(ttl)
        else:
            logger.warning("Cấu hình TICKET_TTL không nhận dạng được: %r, mặc định về end_of_day", TICKET_TTL)
    except (ValueError, TypeError):
        logger.warning("Cấu hình TICKET_TTL không hợp lệ: %r, mặc định về end_of_day", TICKET_TTL)
        seconds = None
    if seconds is None:
        return local.replace(hour=23, minute=59, second=59, microsecond=0)
    return local + timedelta(seconds=seconds)


def generate_ticket_code() -> str:
    part = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(12))
    return f"ZCV-{part[:4]}-{part[4:8]}-{part[8:]}"


def ticket_status(ticket: dict, at: Optional[datetime] = None) -> str:
    if ticket.get("cancelled_at"):
        return "cancelled"
    at = at or now_vn()
    expires = ticket["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if at.astimezone(VN_TZ) >= expires.astimezone(VN_TZ):
        return "expired"
    if ticket.get("device_id"):
        return "activated"
    return "unused"


def make_ticket_token(ticket_id: str, device_id: str, token_version: int, expires_at: datetime) -> str:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    payload = {
        "type": "ticket",
        "sub": ticket_id,
        "ticket_id": ticket_id,
        "device_id": device_id,
        "token_version": token_version,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at.astimezone(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


STATUS_LABELS = {
    "unused": "chưa kích hoạt",
    "activated": "đã kích hoạt",
    "expired": "hết hạn",
    "cancelled": "đã hủy",
}


def serialize_ticket(ticket: dict) -> dict:
    status = ticket_status(ticket)
    return {
        "id": ticket["id"],
        "code": ticket["code"],
        "created_by": ticket.get("created_by"),
        "created_at": to_iso(ticket.get("created_at")),
        "expires_at": to_iso(ticket.get("expires_at")),
        "status": status,
        "status_label": STATUS_LABELS[status],
        "device_id": ticket.get("device_id"),
        "activated_at": to_iso(ticket.get("activated_at")),
        "cancelled_at": to_iso(ticket.get("cancelled_at")),
        "token_version": ticket.get("token_version", 0),
    }


def ticket_error(status: int, error: str, message: str, **extra) -> None:
    raise HTTPException(status_code=status, detail={"error": error, "message": message, **extra})


def check_activate_rate_limit(request: Request, device_id: str) -> None:
    """Giới hạn theo IP và theo cặp IP+device để giảm đoán mã."""
    ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).timestamp()
    keys = ((ip, ACTIVATE_IP_RATE_LIMIT), (f"{ip}:{device_id or '-'}", ACTIVATE_RATE_LIMIT))
    with _rate_lock:
        for key, limit in keys:
            hits = _rate_hits[key]
            while hits and now - hits[0] > ACTIVATE_RATE_WINDOW_SEC:
                hits.popleft()
            if len(hits) >= limit:
                ticket_error(429,"rate_limit_exceeded","Thử quá nhiều lần, vui lòng đợi ít phút",)  
            hits.append(now)


def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


async def activate_ticket(db, code: str, device_id: str, confirm_device_switch: bool = False) -> dict:
    """
    Giả định đổi máy:
    - Máy A kích hoạt lần đầu → gắn device_id, token_version = 1.
    - Cùng device_id gọi lại → cấp JWT mới, không tăng version (idempotent).
    - Máy B gọi với code đúng, confirm_device_switch=false → 409 used_on_other_device.
      Client hiện xác nhận rồi gọi lại với confirm_device_switch=true.
    - Khi xác nhận đổi máy: tăng token_version, gắn device mới; JWT máy cũ hết hiệu lực.
    """
    code = normalize_code(code)
    device_id = (device_id or "").strip()
    if not code or not device_id:
        ticket_error(400, "invalid_request", "Cần code và device_id")

    ticket = await db["tickets"].find_one({"code": code})
    if not ticket:
        ticket_error(404, "invalid_code", "Mã vé không đúng")

    if ticket.get("cancelled_at"):
        ticket_error(410, "ticket_cancelled", "Vé đã bị hủy")

    if ticket_status(ticket) == "expired":
        ticket_error(410, "expired", "Vé đã hết hạn")

    bound = ticket.get("device_id")
    version = int(ticket.get("token_version") or 0)

    if bound and bound != device_id and not confirm_device_switch:
        ticket_error(
            409,
            "used_on_other_device",
            "Vé đã kích hoạt trên máy khác. Gửi lại với confirm_device_switch=true để chuyển máy.",
            confirm_required=True,
        )

    now = now_vn()
    if not bound:
        new_expires_at = now + timedelta(seconds=ACTIVATED_TICKET_TTL_SECONDS)
        res = await db["tickets"].update_one(
            {"id": ticket["id"], "device_id": None},
            {
                "$set": {
                    "device_id": device_id,
                    "activated_at": now,
                    "token_version": 1,
                    "expires_at": new_expires_at,
                }
            },
        )
        if res.matched_count == 0:
            fresh = await db["tickets"].find_one({"id": ticket["id"]})
            if fresh and fresh.get("device_id") == device_id:
                ticket = fresh
            else:
                ticket_error(
                    409,
                    "used_on_other_device",
                    "Vé đã kích hoạt trên máy khác. Gửi lại với confirm_device_switch=true để chuyển máy.",
                    confirm_required=True,
                )
    elif bound != device_id:
        res = await db["tickets"].update_one(
            {"id": ticket["id"], "token_version": version},
            {"$set": {"device_id": device_id, "activated_at": now, "token_version": version + 1}},
        )
        if res.matched_count == 0:
            fresh = await db["tickets"].find_one({"id": ticket["id"]})
            if fresh and fresh.get("device_id") == device_id:
                ticket = fresh
            else:
                ticket_error(
                    409,
                    "used_on_other_device",
                    "Vé đã kích hoạt trên máy khác. Gửi lại với confirm_device_switch=true để chuyển máy.",
                    confirm_required=True,
                )
    else:
        await db["tickets"].update_one(
            {"id": ticket["id"]},
            {"$set": {"activated_at": now}},
        )

    invalidate_ticket_cache(ticket["id"])
    ticket = await db["tickets"].find_one({"id": ticket["id"]})
    token = make_ticket_token(ticket["id"], device_id, int(ticket["token_version"]), ticket["expires_at"])
    return {
        "ticket_token": token,
        "expires_at": to_iso(ticket["expires_at"]),
        "status": ticket_status(ticket),
        "token_version": int(ticket["token_version"]),
        "device_id": device_id,
        "ticket": serialize_ticket(ticket),
    }


async def create_ticket_doc(db, created_by: str) -> dict:
    created = now_vn()
    expires = compute_expires_at(created)
    for _ in range(8):
        code = generate_ticket_code()
        if not await db["tickets"].find_one({"code": code}):
            break
    else:
        ticket_error(500, "code_generation_failed", "Không tạo được mã vé duy nhất")

    ticket = {
        "id": str(uuid.uuid4()),
        "code": code,
        "created_by": created_by,
        "created_at": created,
        "expires_at": expires,
        "device_id": None,
        "activated_at": None,
        "token_version": 0,
    }
    await db["tickets"].insert_one(ticket)
    return ticket


def activation_url(code: str) -> str:
    return f"{PUBLIC_BASE_URL}/activate?code={code}"


def vn_day_bounds(day: Optional[datetime] = None) -> tuple[datetime, datetime]:
    day = (day or now_vn()).astimezone(VN_TZ)
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end
