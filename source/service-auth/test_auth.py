"""
Test Auth Service — Giai đoạn 1.
Chạy: TESTING=1 JWT_SECRET=test-secret pytest test_auth.py -v
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

os.environ["TESTING"] = "1"
os.environ["JWT_SECRET"] = "test-secret-key-32bytes-for-pytest!!"
os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ["DB_NAME"] = "zoo_test"

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main as auth_main
from jwt_auth import JWT_ALGORITHM, JWT_SECRET, decode_staff_token, decode_ticket_token, set_ticket_lookup
from main import app, check_password, hash_password, make_staff_token
from tickets import VN_TZ, compute_expires_at, generate_ticket_code, ticket_status

client = TestClient(app)

ADMIN_USER = {
    "id": "uid-admin-001",
    "username": "admin",
    "password_hash": hash_password("admin123"),
    "role": "admin",
    "is_active": True,
    "created_at": datetime.now(timezone.utc),
}

COUNTER_USER = {
    "id": "uid-counter-001",
    "username": "counter01",
    "password_hash": hash_password("counter123"),
    "role": "counter",
    "is_active": True,
    "created_at": datetime.now(timezone.utc),
}

LOCKED_USER = {
    "id": "uid-locked-001",
    "username": "locked_user",
    "password_hash": hash_password("pass1234"),
    "role": "counter",
    "is_active": False,
    "created_at": datetime.now(timezone.utc),
}


def _mock_db(find_one_return=None, find_return=None, update_result=1, insert_raises=None):
    db_mock = MagicMock()
    collection = MagicMock()

    async def _find_one(query, *args, **kwargs):
        return find_one_return

    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=find_return or [])

    async def _insert_one(doc):
        if insert_raises:
            raise insert_raises
        result = MagicMock()
        result.inserted_id = "fake_id"
        return result

    update_mock = MagicMock()
    update_mock.matched_count = update_result

    async def _update_one(query, update):
        return update_mock

    collection.find_one = _find_one
    collection.find = MagicMock(return_value=cursor)
    collection.insert_one = _insert_one
    collection.update_one = _update_one
    db_mock.__getitem__ = MagicMock(return_value=collection)
    return db_mock


def _admin_token():
    return make_staff_token("uid-admin-001", "admin", "admin")


def _counter_token():
    return make_staff_token("uid-counter-001", "counter01", "counter")


def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "Auth Service"


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_login_admin_success(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=ADMIN_USER))
    resp = client.post("/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    payload = decode_staff_token(data["token"])
    assert payload["sub"] == "uid-admin-001"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_login_counter_success(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=COUNTER_USER))
    resp = client.post("/login", json={"username": "counter01", "password": "counter123"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "counter"


def test_login_wrong_password(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=ADMIN_USER))
    resp = client.post("/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_user_not_found(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=None))
    resp = client.post("/login", json={"username": "ghost", "password": "pass"})
    assert resp.status_code == 401


def test_login_locked_account(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=LOCKED_USER))
    resp = client.post("/login", json={"username": "locked_user", "password": "pass1234"})
    assert resp.status_code == 403
    assert "khóa" in resp.json()["detail"]


def test_no_register_endpoint():
    resp = client.post("/register", json={"username": "x", "password": "y"})
    assert resp.status_code == 404


def test_jwt_decode_valid_token():
    token = make_staff_token("uid-001", "testuser", "counter")
    payload = decode_staff_token(token)
    assert payload["username"] == "testuser"
    assert payload["role"] == "counter"
    assert payload["type"] == "staff"


def test_jwt_wrong_signature():
    token = jwt.encode(
        {
            "type": "staff",
            "sub": "x",
            "username": "x",
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "other-secret",
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_staff_token(token)
    assert exc.value.status_code == 401


def test_jwt_expired():
    token = jwt.encode(
        {
            "type": "staff",
            "sub": "x",
            "username": "x",
            "role": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_staff_token(token)
    assert exc.value.status_code == 401
    assert "hết hạn" in exc.value.detail


def test_jwt_manager_role_rejected():
    token = jwt.encode(
        {
            "type": "staff",
            "sub": "x",
            "username": "mgr",
            "role": "manager",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_staff_token(token)
    assert exc.value.status_code == 401


def test_get_me_with_valid_token(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=ADMIN_USER))
    resp = client.get("/me", headers={"Authorization": f"Bearer {_admin_token()}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    assert "password_hash" not in resp.json()


def test_get_me_without_token():
    assert client.get("/me").status_code == 401


def test_list_users_admin(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_return=[ADMIN_USER, COUNTER_USER]))
    resp = client.get("/users", headers={"Authorization": f"Bearer {_admin_token()}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


def test_list_users_counter_forbidden():
    resp = client.get("/users", headers={"Authorization": f"Bearer {_counter_token()}"})
    assert resp.status_code == 403


def test_create_user_admin(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db())
    resp = client.post(
        "/users",
        json={"username": "newcounter", "password": "pass1234", "role": "counter"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "counter"
    assert "password_hash" not in resp.json()["user"]


def test_create_user_invalid_role(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db())
    resp = client.post(
        "/users",
        json={"username": "hacker", "password": "pass", "role": "tourist"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 400


def test_create_user_manager_role_rejected(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db())
    resp = client.post(
        "/users",
        json={"username": "mgr", "password": "pass", "role": "manager"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 400


def test_create_user_counter_forbidden():
    resp = client.post(
        "/users",
        json={"username": "x", "password": "x", "role": "counter"},
        headers={"Authorization": f"Bearer {_counter_token()}"},
    )
    assert resp.status_code == 403


def test_toggle_user_status(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=COUNTER_USER))
    resp = client.patch(
        f"/users/{COUNTER_USER['id']}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 200
    assert "khóa" in resp.json()["message"]


def test_admin_cannot_lock_self(monkeypatch):
    monkeypatch.setattr(auth_main, "get_db", lambda: _mock_db(find_one_return=ADMIN_USER))
    resp = client.patch(
        f"/users/{ADMIN_USER['id']}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 400


def test_password_hash_roundtrip():
    hashed = hash_password("secret")
    assert hashed != "secret"
    assert check_password("secret", hashed)
    assert not check_password("other", hashed)


# ---------- Vé (collection tickets) ----------

DEVICE_A = "11111111-1111-4111-8111-111111111111"
DEVICE_B = "22222222-2222-4222-8222-222222222222"


def _matches(doc, query):
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict) and any(op in expected for op in ("$gte", "$lte", "$gt", "$lt")):
            if "$gte" in expected and not (actual >= expected["$gte"]):
                return False
            if "$lte" in expected and not (actual <= expected["$lte"]):
                return False
            if "$gt" in expected and not (actual > expected["$gt"]):
                return False
            if "$lt" in expected and not (actual < expected["$lt"]):
                return False
        elif actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, *args, **kwargs):
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)
        result = MagicMock()
        result.inserted_id = doc.get("id")
        return result

    async def update_one(self, query, update):
        matched = 0
        for doc in self.docs:
            if _matches(doc, query):
                matched = 1
                if "$set" in update:
                    doc.update(update["$set"])
                if "$inc" in update:
                    for key, value in update["$inc"].items():
                        doc[key] = doc.get(key, 0) + value
                break
        result = MagicMock()
        result.matched_count = matched
        return result

    def find(self, query=None):
        query = query or {}
        return FakeCursor([d for d in self.docs if _matches(d, query)])


class FakeDB:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


@pytest.fixture
def ticket_db(monkeypatch):
    store = FakeDB()
    monkeypatch.setattr(auth_main, "get_db", lambda: store)

    async def _lookup(ticket_id: str):
        return await store["tickets"].find_one({"id": ticket_id})

    set_ticket_lookup(_lookup)
    yield store
    set_ticket_lookup(None)


def _create_ticket(ticket_db, token=None):
    token = token or _counter_token()
    resp = client.post("/tickets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_ticket_counter(ticket_db):
    data = _create_ticket(ticket_db)
    assert data["code"].startswith("ZCV-")
    assert len(data["code"]) >= 15
    assert data["status"] == "unused"
    assert data["status_label"] == "chưa kích hoạt"
    assert data["created_by"] == "counter01"
    assert data["activation_url"].endswith(f"/activate?code={data['code']}")
    assert data["token_version"] == 0
    assert "ZCV-" in data["activation_url"]


def test_create_ticket_requires_staff():
    assert client.post("/tickets").status_code == 401


def test_list_tickets_today(ticket_db):
    created = _create_ticket(ticket_db)
    resp = client.get("/tickets/today", headers={"Authorization": f"Bearer {_counter_token()}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert any(t["code"] == created["code"] for t in body["tickets"])


def test_activate_success(ticket_db):
    created = _create_ticket(ticket_db)
    resp = client.post(
        "/tickets/activate",
        json={"code": created["code"], "device_id": DEVICE_A},
    )
    assert resp.status_code == 200
    body = resp.json()
    token = body["ticket_token"]
    payload = decode_ticket_token(token)
    assert payload["type"] == "ticket"
    assert payload["device_id"] == DEVICE_A
    assert payload["token_version"] == 1
    assert payload["ticket_id"] == created["id"]
    me = client.get("/tickets/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["status"] == "activated"
    assert me.json()["expires_at"] is not None


def test_activate_invalid_code(ticket_db):
    resp = client.post(
        "/tickets/activate",
        json={"code": "ZCV-XXXX-XXXX-XXXX", "device_id": DEVICE_A},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "invalid_code"


def test_activate_expired(ticket_db):
    created = _create_ticket(ticket_db)
    ticket = ticket_db["tickets"].docs[0]
    ticket["expires_at"] = datetime.now(VN_TZ) - timedelta(minutes=1)
    resp = client.post(
        "/tickets/activate",
        json={"code": created["code"], "device_id": DEVICE_A},
    )
    assert resp.status_code == 410
    assert resp.json()["detail"]["error"] == "expired"


def test_activate_other_device_requires_confirm(ticket_db):
    created = _create_ticket(ticket_db)
    first = client.post(
        "/tickets/activate",
        json={"code": created["code"], "device_id": DEVICE_A},
    )
    assert first.status_code == 200
    other = client.post(
        "/tickets/activate",
        json={"code": created["code"], "device_id": DEVICE_B},
    )
    assert other.status_code == 409
    assert other.json()["detail"]["error"] == "used_on_other_device"
    assert other.json()["detail"]["confirm_required"] is True


def test_device_switch_invalidates_old_token(ticket_db):
    created = _create_ticket(ticket_db)
    first = client.post(
        "/tickets/activate",
        json={"code": created["code"], "device_id": DEVICE_A},
    ).json()
    old_token = first["ticket_token"]
    switched = client.post(
        "/tickets/activate",
        json={
            "code": created["code"],
            "device_id": DEVICE_B,
            "confirm_device_switch": True,
        },
    )
    assert switched.status_code == 200
    new_body = switched.json()
    assert new_body["token_version"] == 2
    assert new_body["device_id"] == DEVICE_B

    stale = client.get("/tickets/me", headers={"Authorization": f"Bearer {old_token}"})
    assert stale.status_code == 401
    assert "thay thế" in stale.json()["detail"]

    fresh = client.get("/tickets/me", headers={"Authorization": f"Bearer {new_body['ticket_token']}"})
    assert fresh.status_code == 200
    assert fresh.json()["device_id"] == DEVICE_B


def test_ticket_expires_end_of_day_vietnam():
    created = datetime(2026, 10, 23, 8, 15, 30, tzinfo=VN_TZ)
    expires = compute_expires_at(created)
    assert expires.year == 2026
    assert expires.month == 10
    assert expires.day == 23
    assert expires.hour == 23
    assert expires.minute == 59
    assert expires.second == 59
    assert expires.utcoffset() == timedelta(hours=7)

    still_valid = datetime(2026, 10, 23, 23, 59, 59, tzinfo=VN_TZ)
    too_late = datetime(2026, 10, 24, 0, 0, 0, tzinfo=VN_TZ)
    ticket = {"expires_at": expires, "device_id": None}
    assert ticket_status(ticket, at=still_valid) == "unused"
    assert ticket_status(ticket, at=too_late) == "expired"


def test_generate_ticket_code_format():
    code = generate_ticket_code()
    parts = code.split("-")
    assert parts[0] == "ZCV"
    assert all(len(p) == 4 for p in parts[1:])
    assert len("".join(parts[1:])) == 12
