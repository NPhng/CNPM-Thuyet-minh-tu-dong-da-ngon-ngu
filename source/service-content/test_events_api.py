import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32bytes-for-pytest!!")

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

import main
from jwt_auth import JWT_ALGORITHM, JWT_SECRET

VN = timezone(timedelta(hours=7))
NOW = datetime(2026, 10, 23, 14, 0, 0, tzinfo=VN).astimezone(timezone.utc)
GATE = (10.78755, 106.70528)  # tcv-001, radius_m = 35


class Clock:
    def __init__(self, t):
        self.t = t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def _jwt(payload: dict) -> str:
    payload = {**payload, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def ticket_auth(ticket_id="t1", version=1):
    token = _jwt({"type": "ticket", "sub": ticket_id, "ticket_id": ticket_id, "token_version": version})
    return {"Authorization": f"Bearer {token}"}


def staff_auth(role):
    token = _jwt({"type": "staff", "sub": "u1", "username": role, "role": role})
    return {"Authorization": f"Bearer {token}"}


ADMIN, COUNTER = staff_auth("admin"), staff_auth("counter")


@pytest.fixture
def api(monkeypatch):
    clock = Clock(NOW)
    monkeypatch.setattr(main, "now_utc", lambda: clock.t)
    with TestClient(main.app) as c:
        c.clock = clock
        for i, ago in enumerate([timedelta(hours=3), timedelta(hours=2), timedelta(minutes=30)], start=1):
            main.ticket_store.add({"id": f"t{i}", "token_version": 1, "created_at": NOW - ago})
        yield c


def post(api, poi_id="tcv-001", type="listen", ticket="t1", **extra):
    return api.post("/events", json={"poi_id": poi_id, "type": type, **extra}, headers=ticket_auth(ticket))


# ---------------------------------------------------------------- POST /events

def test_post_event_requires_valid_ticket_token(api):
    body = {"poi_id": "tcv-001", "type": "listen"}
    assert api.post("/events", json=body).status_code == 401
    assert api.post("/events", json=body, headers=ADMIN).status_code == 401  # staff token không dùng được
    assert api.post("/events", json=body, headers={"Authorization": "Bearer rac"}).status_code == 401


def test_post_event_rejects_replaced_or_unknown_ticket(api):
    assert api.post("/events", json={"poi_id": "tcv-001", "type": "listen"}, headers=ticket_auth("t1", version=0)).status_code == 401
    assert api.post("/events", json={"poi_id": "tcv-001", "type": "listen"}, headers=ticket_auth("khong-co")).status_code == 401


def test_post_event_ok_and_ts_in_vietnam_time(api):
    r = post(api, type="listen")
    assert r.status_code == 201
    data = r.json()
    assert data["deduplicated"] is False
    assert data["event"]["ticket_id"] == "t1" and data["event"]["poi_id"] == "tcv-001"
    assert data["event"]["type"] == "listen"
    assert data["event"]["ts"] == "2026-10-23T14:00:00+07:00"
    assert main.event_store.docs[0]["ts"] == NOW  # lưu UTC, thời điểm không đổi


@pytest.mark.parametrize("etype", ["listen", "enter", "exit"])
def test_post_event_accepts_all_three_types(api, etype):
    assert post(api, type=etype).status_code == 201


def test_post_event_unknown_poi_is_404(api):
    r = post(api, poi_id="khong-ton-tai")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "poi_not_found"
    assert main.event_store.docs == []


def test_post_event_validation(api):
    h = ticket_auth()
    assert api.post("/events", json={"poi_id": "tcv-001", "type": "visit"}, headers=h).status_code == 422
    assert api.post("/events", json={"type": "listen"}, headers=h).status_code == 422
    assert api.post("/events", json={"poi_id": "tcv-001", "type": "enter", "lat": 10.78}, headers=h).status_code == 422
    assert api.post("/events", json={"poi_id": "tcv-001", "type": "enter", "lat": 95, "lon": 106}, headers=h).status_code == 422


def test_enter_far_from_poi_is_rejected_when_gps_given(api):
    r = post(api, type="enter", lat=GATE[0] + 0.001, lon=GATE[1])  # ~111 m > 35 + 20
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "out_of_range"
    assert main.event_store.docs == []


def test_enter_inside_poi_is_accepted_with_distance(api):
    r = post(api, type="enter", lat=GATE[0], lon=GATE[1])
    assert r.status_code == 201
    assert r.json()["event"]["in_zone"] is True
    assert r.json()["event"]["distance_m"] == 0


def test_listen_far_away_is_recorded_but_flagged(api):
    r = post(api, type="listen", lat=GATE[0] + 0.001, lon=GATE[1])
    assert r.status_code == 201
    assert r.json()["event"]["in_zone"] is False


def test_duplicate_burst_returns_200_and_stores_once(api):
    first = post(api)
    again = post(api)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["deduplicated"] is True
    assert again.json()["event"]["id"] == first.json()["event"]["id"]
    assert len(main.event_store.docs) == 1
    api.clock.advance(seconds=30)  # đúng EVENT_DEDUPE_SECONDS mặc định
    assert post(api).status_code == 201
    assert len(main.event_store.docs) == 2


def test_enter_exit_enter_rapid_succession_api(api):
    # enter -> exit -> enter nhanh đều được ghi nhận đủ (201) vì sự kiện liền kề khác loại
    r1 = post(api, type="enter")
    assert r1.status_code == 201
    assert r1.json()["deduplicated"] is False

    r2 = post(api, type="exit")
    assert r2.status_code == 201
    assert r2.json()["deduplicated"] is False

    r3 = post(api, type="enter")
    assert r3.status_code == 201
    assert r3.json()["deduplicated"] is False
    assert len(main.event_store.docs) == 3


def test_concurrent_identical_events_api(api):
    import asyncio
    async def _concurrent():
        return await asyncio.gather(*[
            main.ingestor.record(
                ticket_id="t_conc",
                poi={"id": "tcv-001", "lat": GATE[0], "lon": GATE[1], "radius_m": 30},
                event_type="listen",
            )
            for _ in range(5)
        ])

    res = asyncio.run(_concurrent())
    is_new = [r for r, dup in res if not dup]
    is_dup = [r for r, dup in res if dup]
    assert len(is_new) == 1
    assert len(is_dup) == 4


def test_rate_limit_returns_429_with_retry_after(api, monkeypatch):
    monkeypatch.setenv("EVENT_RATE_LIMIT", "2")
    assert post(api, poi_id="tcv-001").status_code == 201
    assert post(api, poi_id="tcv-002").status_code == 201
    r = post(api, poi_id="tcv-003")
    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "rate_limited"
    assert int(r.headers["retry-after"]) >= 1
    assert post(api, poi_id="tcv-003", ticket="t2").status_code == 201  # vé khác không bị ảnh hưởng


# ---------------------------------------------------------------- phân quyền admin

ADMIN_ONLY = ["/events", "/stats/overview", "/stats/pois", "/stats/hourly", "/stats/dashboard"]


@pytest.mark.parametrize("path", ADMIN_ONLY)
def test_admin_endpoints_reject_others(api, path):
    assert api.get(path).status_code == 401
    assert api.get(path, headers=ticket_auth()).status_code == 401
    assert api.get(path, headers=COUNTER).status_code == 403
    assert api.get(path, headers=ADMIN).status_code == 200


# ---------------------------------------------------------------- số liệu qua HTTP

def stat(api, name):
    return api.get(f"/stats/{name}", headers=ADMIN).json()


def gate_row(api):
    return next(r for r in stat(api, "pois")["pois"] if r["poi_id"] == "tcv-001")


def test_stats_follow_events_and_n_minute_boundary(api):
    assert stat(api, "overview")["tickets_sold_today"] == 3
    assert stat(api, "overview")["active_tickets"] == 0

    assert post(api, type="enter", ticket="t1").status_code == 201   # T0
    assert post(api, type="listen", ticket="t2").status_code == 201  # T0
    assert stat(api, "overview")["active_tickets"] == 2
    row = gate_row(api)
    assert row["present_now"] == 2 and row["passes_today"] == 2

    api.clock.advance(minutes=1)
    assert post(api, type="exit", ticket="t1").status_code == 201    # T0 + 1 phút
    row = gate_row(api)
    assert row["present_now"] == 1          # t1 đã exit, t2 vừa nghe
    assert row["passes_today"] == 2         # exit không làm giảm lượt đi qua

    api.clock.advance(minutes=9)            # T0 + 10 phút: listen của t2 đúng mốc N
    assert stat(api, "overview")["active_tickets"] == 2
    assert gate_row(api)["present_now"] == 1

    api.clock.advance(seconds=1)            # lố mốc N của listen t2
    assert stat(api, "overview")["active_tickets"] == 1  # chỉ còn t1 (exit lúc T0+1')
    assert gate_row(api)["present_now"] == 0

    api.clock.advance(minutes=1)            # T0 + 11'01'': exit của t1 cũng quá N
    assert stat(api, "overview")["active_tickets"] == 0


def test_n_active_minutes_env_changes_the_window(api, monkeypatch):
    post(api, type="listen", ticket="t1")
    api.clock.advance(minutes=6)
    assert stat(api, "overview")["active_tickets"] == 1
    monkeypatch.setenv("N_ACTIVE_MINUTES", "5")
    data = stat(api, "overview")
    assert data["n_active_minutes"] == 5 and data["active_tickets"] == 0


def test_stats_pois_lists_every_poi_with_definitions(api):
    data = stat(api, "pois")
    assert len(data["pois"]) == len(api.get("/pois").json()["pois"]) >= 15
    assert {"present_now", "passes_today"} <= set(data["definition"])
    assert all({"poi_id", "name", "present_now", "passes_today"} <= set(r) for r in data["pois"])


def test_hourly_series_today_and_by_date(api):
    post(api, type="enter", ticket="t1")  # 14:00 VN
    data = stat(api, "hourly")
    assert data["day"]["date"] == "2026-10-23" and len(data["hours"]) == 24
    assert data["hours"][14]["events"]["enter"] == 1
    assert data["hours"][14]["active_tickets"] == 1 and data["hours"][14]["visits"] == 1
    assert data["totals"]["tickets_sold"] == 3

    other = api.get("/stats/hourly?date=2026-10-22", headers=ADMIN).json()
    assert other["totals"] == {"tickets_sold": 0, "events": 0}
    assert api.get("/stats/hourly?date=khong-phai-ngay", headers=ADMIN).status_code == 422


def test_hourly_uses_vn_day_not_utc_day(api):
    # 00:30 giờ VN ngày 24 = 17:30 UTC ngày 23: thuộc ngày 24 theo giờ VN
    api.clock.t = datetime(2026, 10, 24, 0, 30, tzinfo=VN).astimezone(timezone.utc)
    post(api, type="listen", ticket="t1")
    day24 = api.get("/stats/hourly?date=2026-10-24", headers=ADMIN).json()
    day23 = api.get("/stats/hourly?date=2026-10-23", headers=ADMIN).json()
    assert day24["hours"][0]["events"]["listen"] == 1
    assert day23["totals"]["events"] == 0


def test_dashboard_returns_three_sections(api):
    post(api, type="enter", ticket="t1")
    data = stat(api, "dashboard")
    assert set(data) == {"overview", "pois", "hourly"}
    assert data["overview"]["active_tickets"] == 1
    assert data["pois"]["present_total"] == 1


def test_events_listing_newest_first_with_filters(api):
    post(api, poi_id="tcv-001", type="enter", ticket="t1")
    api.clock.advance(minutes=1)
    post(api, poi_id="tcv-002", type="enter", ticket="t2")
    api.clock.advance(minutes=1)
    post(api, poi_id="tcv-002", type="listen", ticket="t1")

    events = api.get("/events", headers=ADMIN).json()["events"]
    assert [e["type"] for e in events] == ["listen", "enter", "enter"]
    assert all(e["ts"].endswith("+07:00") for e in events)
    assert len(api.get("/events?ticket_id=t1", headers=ADMIN).json()["events"]) == 2
    assert len(api.get("/events?poi_id=tcv-002&limit=1", headers=ADMIN).json()["events"]) == 1
    assert api.get("/events?limit=0", headers=ADMIN).status_code == 422
