"""
Test logic giai đoạn 4 (không cần FastAPI/Mongo): thống kê, ranh giới N phút, ranh giới ngày VN,
kiểm tra GPS, chống trùng, rate limit. Chạy: pytest test_events_logic.py -v
"""

import asyncio
import os
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

import stats
from event_service import EventIngestor
from event_store import MemoryEventStore, MemoryTicketStore
from events_core import (
    VN_TZ,
    EventError,
    Settings,
    SlidingWindowLimiter,
    check_geo,
    haversine_m,
    is_duplicate,
    load_settings,
    to_vn_iso,
    vn_day_range_utc,
)

run = asyncio.run

S = Settings(
    n_active_minutes=10,
    presence_enter_ttl_minutes=120,
    dedupe_seconds=30,
    geo_tolerance_m=20.0,
    rate_limit=30,
    rate_window_sec=60,
    require_gps=False,
)


def vn(y, m, d, h=0, mi=0, s=0, us=0):
    return datetime(y, m, d, h, mi, s, us, tzinfo=VN_TZ)


NOW = vn(2026, 10, 23, 14, 0, 0)
POIS = [{"id": "p1", "name": "Điểm 1"}, {"id": "p2", "name": "Điểm 2"}]


def mins(m=0, s=0, us=0):
    return timedelta(minutes=m, seconds=s, microseconds=us)


def ev(ticket, poi, typ, at, in_zone=None):
    return {"id": f"{ticket}-{poi}-{typ}-{at.isoformat()}", "ticket_id": ticket, "poi_id": poi,
            "type": typ, "ts": at, "in_zone": in_zone}


def ticket(tid, created_at):
    return {"id": tid, "created_at": created_at}


def stores(events=(), tickets=()):
    es, ts = MemoryEventStore(), MemoryTicketStore()
    run(es.insert_many(list(events)))
    for t in tickets:
        ts.add(t)
    return es, ts


@contextmanager
def env(**values):
    old = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------- cấu hình / thời gian

def test_settings_defaults_and_invalid_values():
    with env(N_ACTIVE_MINUTES=None, PRESENCE_ENTER_TTL_MINUTES=None):
        assert load_settings().n_active_minutes == 10
    with env(N_ACTIVE_MINUTES="5"):
        assert load_settings().n_active_minutes == 5
    with env(N_ACTIVE_MINUTES="abc"):
        assert load_settings().n_active_minutes == 10
    with env(N_ACTIVE_MINUTES="0"):
        assert load_settings().n_active_minutes == 1
    with env(N_ACTIVE_MINUTES="200", PRESENCE_ENTER_TTL_MINUTES="120"):
        s = load_settings()
        assert s.presence_enter_ttl_minutes == 200  # TTL không ngắn hơn N


def test_vn_day_range_is_utc_plus_7_half_open():
    start, end = vn_day_range_utc(date(2026, 10, 23))
    assert start == datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc)


def test_ts_is_displayed_in_vietnam_time():
    utc = datetime(2026, 10, 23, 7, 5, tzinfo=timezone.utc)
    assert to_vn_iso(utc) == "2026-10-23T14:05:00+07:00"
    assert to_vn_iso(datetime(2026, 10, 23, 7, 5)) == "2026-10-23T14:05:00+07:00"  # naive = UTC (Mongo)


# ---------------------------------------------------------------- vé bán hôm nay + ranh giới ngày VN

def _boundary_tickets():
    return [
        ticket("A", vn(2026, 10, 22, 23, 59, 59, 999999)),  # hôm qua
        ticket("B", vn(2026, 10, 23, 0, 0, 0)),              # đầu ngày 23
        ticket("C", vn(2026, 10, 23, 13, 59)),
        ticket("D", vn(2026, 10, 24, 0, 0, 0)),              # đầu ngày 24
    ]


def test_tickets_sold_today_respects_vn_midnight():
    es, ts = stores(tickets=_boundary_tickets())
    assert run(stats.build_overview(es, ts, NOW, S))["tickets_sold_today"] == 2  # B, C
    last_us = vn(2026, 10, 23, 23, 59, 59, 999999)
    assert run(stats.build_overview(es, ts, last_us, S))["tickets_sold_today"] == 2
    midnight = vn(2026, 10, 24, 0, 0, 0)
    assert run(stats.build_overview(es, ts, midnight, S))["tickets_sold_today"] == 1  # chỉ D


def test_tickets_created_at_naive_utc_from_mongo_is_handled():
    # 2026-10-22 17:00 UTC (naive, như Mongo trả) = 00:00 ngày 23 giờ VN
    es, ts = stores(tickets=[ticket("N", datetime(2026, 10, 22, 17, 0, 0)),
                             ticket("M", datetime(2026, 10, 22, 16, 59, 59))])
    assert run(stats.build_overview(es, ts, NOW, S))["tickets_sold_today"] == 1


# ---------------------------------------------------------------- vé đang hoạt động / ranh giới N phút

def _active_events():
    return [
        ev("a", "p1", "listen", NOW - mins(10)),                # đúng mốc N -> tính
        ev("b", "p1", "listen", NOW - mins(10, us=1)),          # lố 1 micro giây -> không
        ev("c", "p1", "enter", NOW - mins(1)),
        ev("c", "p2", "listen", NOW - mins(0, 30)),             # cùng vé, đếm 1 lần
        ev("d", "p1", "exit", NOW - mins(3)),                   # exit cũng là hoạt động
        ev("e", "p1", "listen", NOW + mins(0, 1)),              # tương lai -> không
        ev("f", "p1", "listen", NOW),                           # đúng bây giờ -> tính
    ]


def test_active_tickets_n_minute_boundary():
    es, ts = stores(_active_events())
    assert run(stats.build_overview(es, ts, NOW, S))["active_tickets"] == 4  # a, c, d, f


def test_active_tickets_follows_n_setting():
    es, ts = stores(_active_events())
    assert run(stats.build_overview(es, ts, NOW, replace(S, n_active_minutes=5)))["active_tickets"] == 3  # c, d, f
    assert run(stats.build_overview(es, ts, NOW, replace(S, n_active_minutes=1)))["active_tickets"] == 2   # c, f
    assert run(stats.build_overview(es, ts, NOW, replace(S, n_active_minutes=11)))["active_tickets"] == 5  # + b
    data = run(stats.build_overview(es, ts, NOW, replace(S, n_active_minutes=5)))
    assert data["n_active_minutes"] == 5
    assert data["active_window"]["from"] == "2026-10-23T13:55:00+07:00"


def test_active_tickets_window_crosses_midnight():
    now = vn(2026, 10, 24, 0, 3)
    es, ts = stores([ev("x", "p1", "listen", vn(2026, 10, 23, 23, 58))])
    assert run(stats.build_overview(es, ts, now, S))["active_tickets"] == 1


# ---------------------------------------------------------------- đang ở trong điểm

def _presence_events():
    e = []
    e += [ev("A", "p1", "enter", NOW - mins(30))]                                           # (a) enter chưa exit
    e += [ev("B", "p1", "enter", NOW - mins(30)), ev("B", "p1", "exit", NOW - mins(5))]     # đã exit
    e += [ev("C", "p1", "enter", NOW - mins(30)), ev("C", "p1", "exit", NOW - mins(20)),
          ev("C", "p1", "listen", NOW - mins(5))]                                           # (b) hoạt động sau exit
    e += [ev("D", "p1", "listen", NOW - mins(9, 59))]                                       # trong N
    e += [ev("E", "p1", "listen", NOW - mins(10, 1))]                                       # quá N
    e += [ev("E2", "p1", "listen", NOW - mins(10))]                                         # đúng mốc N
    e += [ev("F", "p1", "enter", NOW - mins(121))]                                          # quá TTL
    e += [ev("G", "p1", "enter", NOW - mins(120))]                                          # đúng mốc TTL
    e += [ev("H", "p1", "enter", NOW - mins(30)), ev("H", "p1", "listen", NOW - mins(15))]  # listen cũ nhưng chưa exit
    e += [ev("I", "p1", "listen", NOW - mins(5)), ev("I", "p1", "exit", NOW - mins(1))]     # exit sau cùng
    e += [ev("J", "p1", "enter", NOW - mins(20)), ev("J", "p2", "enter", NOW - mins(5))]    # hai điểm -> chỉ p2
    e += [ev("K", "p1", "listen", NOW - mins(2), in_zone=False)]                            # nghe từ xa
    e += [ev("L", "p1", "exit", NOW - mins(2))]                                             # chỉ exit
    e += [ev("M", "p1", "enter", NOW - mins(50)), ev("M", "p1", "exit", NOW - mins(40)),
          ev("M", "p1", "enter", NOW - mins(20))]                                           # vào lại
    e += [ev("N", "p1", "enter", NOW - mins(30)),
          ev("N", "p1", "listen", NOW - mins(1), in_zone=False)]                            # listen ngoài vùng bị bỏ qua
    e += [ev("O", "p1", "enter", NOW + mins(1))]                                            # tương lai
    return e


def test_presence_per_poi_matrix():
    es, ts = stores(_presence_events())
    data = run(stats.build_pois(es, POIS, NOW, S))
    by_id = {r["poi_id"]: r for r in data["pois"]}
    # p1: A C D E2 G H M N K = 9 ; p2: J = 1 (K nghe ngoài vùng vẫn tính hoạt động)
    assert by_id["p1"]["present_now"] == 9
    assert by_id["p2"]["present_now"] == 1
    assert data["present_total"] == 10  # mỗi vé chỉ đếm một lần (J không bị đếm ở cả p1 và p2)
    assert [r["poi_id"] for r in data["pois"]] == ["p1", "p2"]  # sắp xếp theo present_now giảm dần


def test_presence_follows_n_and_ttl_settings():
    es, ts = stores([ev("A", "p1", "listen", NOW - mins(7)), ev("B", "p1", "enter", NOW - mins(90))])
    p = lambda s: {r["poi_id"]: r["present_now"] for r in run(stats.build_pois(es, POIS, NOW, s))["pois"]}["p1"]
    assert p(S) == 2
    assert p(replace(S, n_active_minutes=5)) == 1            # A quá N
    assert p(replace(S, presence_enter_ttl_minutes=60)) == 1  # B quá TTL


def test_presence_tie_goes_to_smaller_poi_id():
    es, ts = stores([ev("T", "p2", "enter", NOW - mins(3)), ev("T", "p1", "enter", NOW - mins(3))])
    rows = {r["poi_id"]: r["present_now"] for r in run(stats.build_pois(es, POIS, NOW, S))["pois"]}
    assert rows == {"p1": 1, "p2": 0}


def test_presence_goes_to_poi_with_most_recent_activity():
    # vào p1, vào p2 (không exit p1), rồi quay lại nghe ở p1 -> hoạt động gần nhất ở p1
    es, ts = stores([
        ev("T", "p1", "enter", NOW - mins(20)),
        ev("T", "p2", "enter", NOW - mins(10)),
        ev("T", "p1", "listen", NOW - mins(2)),
    ])
    data = run(stats.build_pois(es, POIS, NOW, S))
    assert {r["poi_id"]: r["present_now"] for r in data["pois"]} == {"p1": 1, "p2": 0}
    assert data["present_total"] == 1


def test_presence_ignores_unknown_poi():
    es, ts = stores([ev("T", "da-xoa", "enter", NOW - mins(1))])
    data = run(stats.build_pois(es, POIS, NOW, S))
    assert data["present_total"] == 0


# ---------------------------------------------------------------- lượt đi qua

def test_passes_are_distinct_tickets_with_listen_or_enter():
    events = [
        ev("X", "p1", "listen", NOW - mins(50)), ev("X", "p1", "listen", NOW - mins(40)),
        ev("X", "p1", "listen", NOW - mins(30)), ev("X", "p1", "enter", NOW - mins(20)),  # 1 vé
        ev("Y", "p1", "exit", NOW - mins(20)),                                            # chỉ exit
        ev("Z", "p1", "listen", NOW - mins(20), in_zone=False),                           # ngoài vùng
        ev("W", "p1", "listen", vn(2026, 10, 22, 23, 59, 59, 999999)),                    # hôm qua
        ev("V", "p1", "enter", vn(2026, 10, 23, 0, 0, 0)),                                # đầu ngày VN
        ev("U", "da-xoa", "listen", NOW - mins(5)),                                       # POI không còn
        ev("X", "p2", "enter", NOW - mins(10)),
        ev("G", "p1", "listen", NOW - mins(5), in_zone=None),                             # không GPS vẫn tính
    ]
    es, ts = stores(events)
    rows = {r["poi_id"]: r["passes_today"] for r in run(stats.build_pois(es, POIS, NOW, S))["pois"]}
    assert rows == {"p1": 4, "p2": 1}  # p1: X, V, G, Z (Z nghe ngoài vùng vẫn tính)


def test_passes_day_boundary_next_day():
    es, ts = stores([ev("W", "p1", "listen", vn(2026, 10, 23, 23, 59, 59, 999999)),
                     ev("V", "p1", "enter", vn(2026, 10, 24, 0, 0, 0))])
    day24 = vn(2026, 10, 24, 0, 30)
    rows = {r["poi_id"]: r["passes_today"] for r in run(stats.build_pois(es, POIS, day24, S))["pois"]}
    assert rows["p1"] == 1  # chỉ V
    day23 = vn(2026, 10, 23, 23, 59, 59, 999999)
    rows = {r["poi_id"]: r["passes_today"] for r in run(stats.build_pois(es, POIS, day23, S))["pois"]}
    assert rows["p1"] == 1  # chỉ W


def test_pois_without_events_are_listed_with_zero():
    es, ts = stores()
    data = run(stats.build_pois(es, POIS, NOW, S))
    assert len(data["pois"]) == 2
    assert all(r["present_now"] == 0 and r["passes_today"] == 0 for r in data["pois"])


# ---------------------------------------------------------------- chuỗi theo giờ

def _hourly_fixture():
    events = [
        ev("t1", "p1", "listen", vn(2026, 10, 23, 7, 59, 59, 999999)),
        ev("t1", "p1", "enter", vn(2026, 10, 23, 8, 0, 0)),
        ev("t1", "p1", "listen", vn(2026, 10, 23, 8, 30)),
        ev("t2", "p2", "listen", vn(2026, 10, 23, 8, 45)),
        ev("t2", "p2", "exit", vn(2026, 10, 23, 8, 59)),
        ev("t5", "p1", "listen", vn(2026, 10, 23, 9, 0), in_zone=False),
        ev("t3", "p1", "enter", vn(2026, 10, 23, 23, 59, 59, 999999)),
        ev("t4", "p1", "enter", vn(2026, 10, 24, 0, 0, 0)),
    ]
    tickets = [
        ticket("s1", vn(2026, 10, 23, 0, 0, 0)),
        ticket("s2", vn(2026, 10, 23, 8, 10)),
        ticket("s3", vn(2026, 10, 23, 8, 20)),
        ticket("s4", vn(2026, 10, 23, 23, 59, 59, 999999)),
        ticket("s5", vn(2026, 10, 22, 23, 59, 59, 999999)),
    ]
    return stores(events, tickets)


def test_hourly_series_for_vn_day():
    es, ts = _hourly_fixture()
    data = run(stats.build_hourly(es, ts, date(2026, 10, 23)))
    h = data["hours"]
    assert len(h) == 24 and [x["hour"] for x in h] == list(range(24))
    assert h[8]["label"] == "08:00"

    assert h[7]["events"] == {"listen": 1, "enter": 0, "exit": 0, "total": 1}
    assert h[7]["active_tickets"] == 1 and h[7]["visits"] == 1

    assert h[8]["events"] == {"listen": 2, "enter": 1, "exit": 1, "total": 4}
    assert h[8]["active_tickets"] == 2          # t1, t2
    assert h[8]["visits"] == 2                  # (t1,p1), (t2,p2) — t1 nghe 2 lần vẫn là 1 cặp
    assert h[8]["tickets_sold"] == 2

    assert h[9]["events"]["listen"] == 1 and h[9]["active_tickets"] == 1
    assert h[9]["visits"] == 1                  # listen ngoài vùng vẫn tính lượt ghé

    assert h[0]["tickets_sold"] == 1 and h[0]["events"]["total"] == 0
    assert h[23]["events"]["enter"] == 1 and h[23]["tickets_sold"] == 1 and h[23]["visits"] == 1

    assert data["totals"] == {"tickets_sold": 4, "events": 7}  # s5 và t4 thuộc ngày khác


def test_hourly_next_day_gets_the_boundary_items():
    es, ts = _hourly_fixture()
    data = run(stats.build_hourly(es, ts, date(2026, 10, 24)))
    assert data["hours"][0]["events"]["enter"] == 1
    assert data["totals"]["events"] == 1
    prev = run(stats.build_hourly(es, ts, date(2026, 10, 22)))
    assert prev["hours"][23]["tickets_sold"] == 1 and prev["totals"]["events"] == 0


def test_dashboard_combines_three_reports():
    es, ts = _hourly_fixture()
    data = run(stats.build_dashboard(es, ts, POIS, vn(2026, 10, 23, 9, 5), S))
    assert set(data) == {"overview", "pois", "hourly"}
    assert data["overview"]["tickets_sold_today"] == 4
    assert data["hourly"]["day"]["date"] == "2026-10-23"
    assert len(data["hourly"]["hours"]) == 24


# ---------------------------------------------------------------- GPS (Haversine)

POI = {"id": "p1", "lat": 10.78755, "lon": 106.70528, "radius_m": 30}
M_PER_DEG_LAT = 6371000.0 * 3.141592653589793 / 180


def at_distance(m):
    return POI["lat"] + m / M_PER_DEG_LAT, POI["lon"]


def test_haversine_known_values():
    assert haversine_m(10.0, 106.0, 10.0, 106.0) == 0
    assert haversine_m(10.0, 106.0, 10.0, 106.001) == pytest.approx(109.5, abs=1.0)
    assert haversine_m(*at_distance(50), POI["lat"], POI["lon"]) == pytest.approx(50, abs=0.01)


def test_enter_must_be_within_radius_plus_tolerance():
    lat, lon = at_distance(49)  # 30 + 20 = 50
    r = check_geo("enter", POI, lat, lon, S)
    assert r.in_zone is True and r.distance_m == pytest.approx(49, abs=0.2)
    lat, lon = at_distance(51)
    with pytest.raises(EventError) as exc:
        check_geo("enter", POI, lat, lon, S)
    assert exc.value.status == 422 and exc.value.code == "out_of_range"


def test_exit_rejected_only_when_deep_inside():
    lat, lon = at_distance(9)  # < 30 - 20
    with pytest.raises(EventError) as exc:
        check_geo("exit", POI, lat, lon, S)
    assert exc.value.code == "still_in_range"
    lat, lon = at_distance(11)
    assert check_geo("exit", POI, lat, lon, S).distance_m == pytest.approx(11, abs=0.2)
    lat, lon = at_distance(200)
    assert check_geo("exit", POI, lat, lon, S).in_zone is False


def test_listen_outside_zone_is_recorded_but_flagged():
    lat, lon = at_distance(200)
    r = check_geo("listen", POI, lat, lon, S)
    assert r.in_zone is False


def test_without_gps_events_are_accepted_unless_required():
    assert check_geo("enter", POI, None, None, S).in_zone is None
    strict = replace(S, require_gps=True)
    with pytest.raises(EventError) as exc:
        check_geo("enter", POI, None, None, strict)
    assert exc.value.code == "gps_required"
    with pytest.raises(EventError):
        check_geo("exit", POI, None, None, strict)
    assert check_geo("listen", POI, None, None, strict).in_zone is None


def test_poi_without_radius_uses_default_30():
    poi = {"id": "x", "lat": POI["lat"], "lon": POI["lon"]}
    lat, lon = at_distance(49)
    assert check_geo("enter", poi, lat, lon, S).in_zone is True
    lat, lon = at_distance(51)
    with pytest.raises(EventError):
        check_geo("enter", poi, lat, lon, S)


# ---------------------------------------------------------------- chống trùng

class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_ingestor(settings=S, start=NOW):
    es = MemoryEventStore()
    clk = Clock(start)
    return EventIngestor(es, clock=clk, settings_fn=lambda: settings), es, clk


def rec(ing, ticket_id="t1", poi=POI, typ="listen", **kw):
    return ing.record(ticket_id=ticket_id, poi=poi, event_type=typ, **kw)


def test_is_duplicate_boundaries():
    last = {"type": "listen", "ts": NOW}
    assert is_duplicate(last, "listen", NOW + timedelta(seconds=29, microseconds=999999), 30) is True
    assert is_duplicate(last, "listen", NOW + timedelta(seconds=30), 30) is False  # đúng window -> không trùng
    assert is_duplicate(last, "enter", NOW, 30) is False
    assert is_duplicate(None, "listen", NOW, 30) is False
    assert is_duplicate(last, "listen", NOW, 0) is False  # tắt chống trùng


def test_duplicate_within_window_is_not_stored_again():
    async def go():
        ing, es, clk = make_ingestor()
        first, dup1 = await rec(ing)
        clk.advance(seconds=29, microseconds=999999)
        again, dup2 = await rec(ing)
        clk.advance(microseconds=1)  # đúng 30 giây kể từ sự kiện đầu
        third, dup3 = await rec(ing)
        return first, dup1, again, dup2, third, dup3, len(es.docs)

    first, dup1, again, dup2, third, dup3, n = run(go())
    assert (dup1, dup2, dup3) == (False, True, False)
    assert again["id"] == first["id"]  # trả lại sự kiện đã có
    assert third["id"] != first["id"]
    assert n == 2


def test_different_type_poi_or_ticket_is_not_duplicate():
    async def go():
        ing, es, clk = make_ingestor()
        other_poi = {**POI, "id": "p2"}
        await rec(ing, typ="listen")
        flags = [
            (await rec(ing, typ="enter"))[1],
            (await rec(ing, poi=other_poi, typ="listen"))[1],
            (await rec(ing, ticket_id="t2", typ="listen"))[1],
        ]
        return flags, len(es.docs)

    flags, n = run(go())
    assert flags == [False, False, False] and n == 4


def test_enter_exit_enter_in_quick_succession_all_recorded():
    async def go():
        ing, es, clk = make_ingestor()
        for typ in ("enter", "exit", "enter"):
            await rec(ing, typ=typ)
            clk.advance(seconds=1)
        return [d["type"] for d in es.docs]

    assert run(go()) == ["enter", "exit", "enter"]


def test_concurrent_identical_requests_store_one_event():
    async def go():
        ing, es, clk = make_ingestor()
        results = await asyncio.gather(*[rec(ing) for _ in range(20)])
        return sum(1 for _, dup in results if dup), len(es.docs)

    dups, n = run(go())
    assert n == 1 and dups == 19


def test_event_uses_server_time_utc_and_keeps_no_raw_gps():
    async def go():
        ing, es, clk = make_ingestor()
        lat, lon = at_distance(10)
        doc, _ = await rec(ing, typ="enter", lat=lat, lon=lon)
        return doc, es.docs[0]

    doc, stored = run(go())
    assert stored["ts"] == NOW and stored["ts"].utcoffset() is not None
    assert stored["in_zone"] is True and stored["distance_m"] == pytest.approx(10, abs=0.2)
    assert "lat" not in stored and "lon" not in stored


def test_rejected_event_is_not_stored():
    async def go():
        ing, es, clk = make_ingestor()
        lat, lon = at_distance(500)
        try:
            await rec(ing, typ="enter", lat=lat, lon=lon)
        except EventError:
            pass
        return len(es.docs)

    assert run(go()) == 0


def test_rate_limit_per_ticket_with_retry_after():
    ing, es, clk = make_ingestor(replace(S, rate_limit=3, rate_window_sec=60))
    for _ in range(3):
        ing.check_rate("t1")
    with pytest.raises(EventError) as exc:
        ing.check_rate("t1")
    assert exc.value.status == 429 and exc.value.code == "rate_limited"
    assert 1 <= int(exc.value.headers["Retry-After"]) <= 60
    ing.check_rate("t2")  # vé khác không bị ảnh hưởng
    clk.advance(seconds=60)
    ing.check_rate("t1")  # hết cửa sổ


def test_sliding_window_limiter_boundary():
    lim = SlidingWindowLimiter()
    assert lim.check("k", 1, 10, NOW) is None
    assert lim.check("k", 1, 10, NOW + timedelta(seconds=9, microseconds=999999)) is not None
    assert lim.check("k", 1, 10, NOW + timedelta(seconds=10)) is None

def test_compute_passes_includes_listen_outside_zone():
    events = [
        {"ticket_id": "t1", "poi_id": "p1", "type": "listen", "in_zone": False},
        {"ticket_id": "t2", "poi_id": "p1", "type": "enter", "in_zone": False},   # enter ngoài vùng không tính
        {"ticket_id": "t3", "poi_id": "p1", "type": "enter", "in_zone": True},    # enter trong vùng tính
    ]
    res = stats.compute_passes(events)
    assert res == {"p1": 2}  # t1 (listen ngoài vùng) và t3 (enter trong vùng)

