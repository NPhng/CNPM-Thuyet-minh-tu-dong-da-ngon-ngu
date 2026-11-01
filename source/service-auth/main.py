"""
Auth Service — đăng nhập nhân viên nội bộ (counter / admin) và vé du khách.

Du khách KHÔNG có tài khoản: quét QR → kích hoạt mã vé → nhận ticket_token.

Biến môi trường: JWT_SECRET, MONGO_URI, DB_NAME, ADMIN_USERNAME, ADMIN_PASSWORD,
PUBLIC_BASE_URL, TICKET_TTL
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
import os
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from jwt_auth import (
    JWT_ALGORITHM,
    JWT_SECRET,
    VALID_ROLES,
    get_current_staff,
    require_roles,
    require_valid_ticket,
    set_ticket_lookup,
)
from tickets import (
    activate_ticket,
    activation_url,
    check_activate_rate_limit,
    create_ticket_doc,
    serialize_ticket,
    to_iso,
    vn_day_bounds,
)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "zoo")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
COUNTER_SEED_USERNAME = os.getenv("COUNTER_USERNAME", "counter01")
COUNTER_SEED_PASSWORD = os.getenv("COUNTER_PASSWORD", "counter123")
TESTING = os.getenv("TESTING", "").lower() in {"1", "true", "yes"}
STAFF_TOKEN_HOURS = int(os.getenv("STAFF_TOKEN_HOURS", "8"))

db_client: Optional[AsyncIOMotorClient] = None


def get_db():
    if db_client is None:
        raise HTTPException(status_code=503, detail="Chưa kết nối cơ sở dữ liệu")
    return db_client[DB_NAME]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def make_staff_token(user_id: str, username: str, role: str) -> str:
    now = now_utc()
    payload = {
        "type": "staff",
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=STAFF_TOKEN_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def serialize_user(user: dict) -> dict:
    created = user.get("created_at")
    if isinstance(created, datetime):
        created = created.isoformat()
    return {
        "id": user.get("id") or str(user.get("_id", "")),
        "username": user["username"],
        "role": user["role"],
        "is_active": user.get("is_active", True),
        "created_at": created,
    }


async def seed_users(db) -> None:
    seeds = [
        {
            "id": str(uuid.uuid4()),
            "username": ADMIN_USERNAME,
            "password_hash": hash_password(ADMIN_PASSWORD),
            "role": "admin",
            "is_active": True,
            "created_at": now_utc(),
        },
        {
            "id": str(uuid.uuid4()),
            "username": COUNTER_SEED_USERNAME,
            "password_hash": hash_password(COUNTER_SEED_PASSWORD),
            "role": "counter",
            "is_active": True,
            "created_at": now_utc(),
        },
    ]
    for user in seeds:
        existing = await db["users"].find_one({"username": user["username"]})
        if not existing:
            await db["users"].insert_one(user)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client
    if TESTING:
        yield
        return
    db_client = AsyncIOMotorClient(MONGO_URI)
    db = db_client[DB_NAME]
    await db["users"].create_index("username", unique=True)
    await db["tickets"].create_index("code", unique=True)
    await db["tickets"].create_index("created_at")
    await seed_users(db)

    async def _lookup(ticket_id: str):
        return await db["tickets"].find_one({"id": ticket_id})

    set_ticket_lookup(_lookup)
    yield
    db_client.close()
    db_client = None


app = FastAPI(
    title="Zoo Auth Service",
    description="Xác thực nhân viên nội bộ — Thảo Cầm Viên Sài Gòn",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str
    token: str
    expires_in: int


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = Field(..., description="counter | admin")


class UserStatusUpdate(BaseModel):
    is_active: bool


class ActivateTicketRequest(BaseModel):
    code: str = Field(..., min_length=4, description="Mã vé in trên QR")
    device_id: str = Field(..., min_length=8, description="UUID do client tự sinh, lưu localStorage")
    confirm_device_switch: bool = Field(
        False,
        description="true = xác nhận chuyển vé sang máy này (vô hiệu token máy cũ)",
    )


@app.get("/")
def root():
    return {"service": "Auth Service", "status": "đang chạy", "version": "2.0.0"}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "auth"}


@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    db = get_db()
    user = await db["users"].find_one({"username": request.username})
    if not user or not check_password(request.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Username hoặc mật khẩu không đúng")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khóa")
    if user.get("role") not in VALID_ROLES:
        raise HTTPException(status_code=403, detail="Tài khoản không có quyền đăng nhập")

    token = make_staff_token(user.get("id") or str(user.get("_id")), user["username"], user["role"])
    return LoginResponse(
        username=user["username"],
        role=user["role"],
        token=token,
        expires_in=STAFF_TOKEN_HOURS * 3600,
    )


@app.get("/me")
async def get_me(payload: dict = Depends(get_current_staff)):
    db = get_db()
    user = await db["users"].find_one({"username": payload["username"]})
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    return serialize_user(user)


@app.get("/users")
async def list_users(_: dict = Depends(require_roles("admin"))):
    db = get_db()
    users = await db["users"].find({}).to_list(length=500)
    return {"total": len(users), "users": [serialize_user(u) for u in users]}


@app.post("/users", status_code=201)
async def create_user(data: UserCreate, payload: dict = Depends(require_roles("admin"))):
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role không hợp lệ. Chọn: {sorted(VALID_ROLES)}")

    db = get_db()
    new_user = {
        "id": str(uuid.uuid4()),
        "username": data.username,
        "password_hash": hash_password(data.password),
        "role": data.role,
        "is_active": True,
        "created_at": now_utc(),
        "created_by": payload.get("username"),
    }
    try:
        await db["users"].insert_one(new_user)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail=f"Username '{data.username}' đã tồn tại")
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(status_code=400, detail=f"Username '{data.username}' đã tồn tại")
        raise
    return {"message": "Tạo tài khoản thành công", "user": serialize_user(new_user)}


@app.patch("/users/{user_id}/status")
async def set_user_status(
    user_id: str,
    body: UserStatusUpdate,
    payload: dict = Depends(require_roles("admin")),
):
    db = get_db()
    target = await db["users"].find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    if target["username"] == payload["username"] and not body.is_active:
        raise HTTPException(status_code=400, detail="Không thể tự khóa tài khoản của chính mình")

    await db["users"].update_one({"id": user_id}, {"$set": {"is_active": body.is_active}})
    action = "mở khóa" if body.is_active else "khóa"
    return {"message": f"Đã {action} tài khoản '{target['username']}'"}


@app.post("/tickets", status_code=201)
async def create_ticket(staff: dict = Depends(require_roles("counter", "admin"))):
    ticket = await create_ticket_doc(get_db(), staff["username"])
    return {
        **serialize_ticket(ticket),
        "activation_url": activation_url(ticket["code"]),
    }


@app.get("/tickets/today")
async def list_tickets_today(_: dict = Depends(require_roles("counter", "admin"))):
    db = get_db()
    start, end = vn_day_bounds()
    docs = await db["tickets"].find({"created_at": {"$gte": start, "$lte": end}}).to_list(length=2000)
    docs.sort(key=lambda t: t.get("created_at") or now_utc(), reverse=True)
    return {"total": len(docs), "tickets": [serialize_ticket(t) for t in docs]}


@app.post("/tickets/activate")
async def activate_ticket_public(body: ActivateTicketRequest, request: Request):
    check_activate_rate_limit(request, body.device_id)
    return await activate_ticket(
        get_db(),
        body.code,
        body.device_id,
        confirm_device_switch=body.confirm_device_switch,
    )


@app.get("/tickets/me")
async def get_my_ticket(ctx: dict = Depends(require_valid_ticket)):
    ticket = ctx["ticket"]
    return {
        "status": serialize_ticket(ticket)["status"],
        "expires_at": to_iso(ticket.get("expires_at")),
        "device_id": ticket.get("device_id"),
        "token_version": ticket.get("token_version", 0),
        "ticket": serialize_ticket(ticket),
    }
