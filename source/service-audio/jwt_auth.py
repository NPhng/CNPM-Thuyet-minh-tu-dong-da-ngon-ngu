"""
jwt_auth.py — Xác thực JWT dùng chung cho cả 3 service.

Mỗi service giữ một bản copy file này. Tất cả đọc JWT_SECRET
và verify tại chỗ — KHÔNG gọi HTTP sang Auth Service.

Role hợp lệ: counter, admin. Không có visitor/tourist/manager.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
JWT_ALGORITHM = "HS256"
_TESTING = os.getenv("TESTING", "").lower() in {"1", "true", "yes"}

# Các giá trị mẫu/công khai: KHÔNG được dùng khi chạy thật.
_WEAK_JWT_SECRETS = {
    "change-me-to-a-long-random-string",
    "zoo-demo-secret-CHANGE-ME-32bytes!!",
    "zoo-demo-secret-key-change-me-32-bytes!!",
}


def _load_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if _TESTING:
        # Chỉ dành cho pytest/CI. Không bao giờ chạy thật với TESTING=1.
        return secret or "test-only-secret-not-for-production-32b"
    if len(secret) < 32 or secret in _WEAK_JWT_SECRETS:
        raise RuntimeError(
            "JWT_SECRET chưa đặt hoặc quá yếu (cần >= 32 ký tự, không dùng giá trị mẫu). "
            'Tạo bằng: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return secret


JWT_SECRET = _load_jwt_secret()
TICKET_LOOKUP_CACHE_TTL = 0.0 if _TESTING else float(os.getenv("TICKET_LOOKUP_CACHE_TTL", "2"))

_bearer_scheme = HTTPBearer(auto_error=False)

VALID_ROLES = {"counter", "admin"}

# Ma trận quyền:
#   counter → tạo vé, xem danh sách vé hôm nay
#   admin   → CRUD POI + quản lý tài khoản + dashboard + mọi quyền của counter


def decode_staff_token(token: str) -> dict:
    """Giải mã JWT nhân viên (type=staff). 401 nếu sai / hết hạn / sai type."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn, vui lòng đăng nhập lại")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    if payload.get("type") != "staff":
        raise HTTPException(status_code=401, detail="Token không phải staff token")
    role = payload.get("role")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail="Role trong token không hợp lệ")
    return payload


def decode_ticket_token(token: str) -> dict:
    """Giải mã JWT vé (type=ticket). Chỉ kiểm tra chữ ký + hạn; token_version đối chiếu DB ở dependency khác."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Vé đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token vé không hợp lệ")

    if payload.get("type") != "ticket":
        raise HTTPException(status_code=401, detail="Token không phải ticket token")
    return payload


def decode_any_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")


async def get_current_staff(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập. Gửi kèm Authorization: Bearer <token>",
        )
    return decode_staff_token(credentials.credentials)


def require_roles(*roles: str):
    """Yêu cầu staff_token có role nằm trong danh sách."""

    async def _check(payload: dict = Depends(get_current_staff)) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Chỉ {'/'.join(roles)} mới có quyền thực hiện thao tác này",
            )
        return payload

    return _check


async def get_ticket_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Chỉ decode ticket JWT (chữ ký + hạn). Caller phải đối chiếu token_version với DB."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Cần vé hợp lệ. Gửi kèm Authorization: Bearer <ticket_token>",
        )
    return decode_ticket_token(credentials.credentials)


_ticket_lookup = None
_ticket_cache: dict[str, tuple[float, Optional[dict]]] = {}


def set_ticket_lookup(fn):
    """Đăng ký hàm async lookup ticket theo id (để đối chiếu token_version)."""
    global _ticket_lookup
    _ticket_lookup = fn


def invalidate_ticket_cache(ticket_id: Optional[str] = None) -> None:
    if ticket_id is None:
        _ticket_cache.clear()
    else:
        _ticket_cache.pop(ticket_id, None)


async def require_valid_ticket(payload: dict = Depends(get_ticket_payload)) -> dict:
    """
    Verify chữ ký JWT, hạn (exp), và token_version còn khớp DB (cache ngắn).
    Trả về {ticket, payload}.
    """
    if _ticket_lookup is None:
        raise HTTPException(status_code=503, detail="Chưa cấu hình kiểm tra vé")
    ticket_id = payload.get("ticket_id") or payload.get("sub")
    now = time.time()
    cached = _ticket_cache.get(ticket_id)
    if cached and TICKET_LOOKUP_CACHE_TTL > 0 and now - cached[0] < TICKET_LOOKUP_CACHE_TTL:
        ticket = cached[1]
    else:
        ticket = await _ticket_lookup(ticket_id)
        _ticket_cache[ticket_id] = (now, ticket)
    if not ticket:
        raise HTTPException(status_code=401, detail="Vé không tồn tại")
    if int(ticket.get("token_version", 0)) != int(payload.get("token_version", 0)):
        raise HTTPException(status_code=401, detail="Token vé đã bị thay thế (đổi máy)")
    return {"ticket": ticket, "payload": payload}
