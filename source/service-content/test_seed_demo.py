"""
Test bộ sinh dữ liệu demo (seed_demo.generate_demo) — không cần Mongo.
Chạy: pytest test_seed_demo.py -v
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import stats
from event_store import MemoryEventStore, MemoryTicketStore
from events_core import VN_TZ, load_settings, vn_day_range_utc
from seed_demo import generate_demo

run = asyncio.run
NOW = datetime(2026, 10, 23, 14, 0, tzinfo=VN_TZ)

_seed_file = Path(__file__).resolve().parent.parent / "seed" / "pois.json"
if not _seed_file.exists():  # khi chạy trong image: /app/seed/pois.json
    _seed_file = Path("/app/seed/pois.json")
POIS = [
    {k: p.get(k) for k in ("id", "name", "category", "lat", "lon", "radius_m")}
    for p in json.loads(_seed_file.read_text(encoding="utf-8"))
]


def _stores(tickets, events):
    es, ts = MemoryEventStore(), MemoryTicketStore()
    run(es.insert_many(events))
    run(ts.insert_many(tickets))
    return es, ts


def test_generation_is_deterministic_per_seed():
    a = generate_demo(POIS, NOW, seed=1)
    b = generate_demo(POIS, NOW, seed=1)
    c = generate_demo(POIS, NOW, seed=2)
    assert a == b
    assert a != c


def test_all_records_valid_and_not_in_the_future():
    tickets, events = generate_demo(POIS, NOW)
    start, end = vn_day_range_utc(NOW.date())
    ids = {t["id"] for t in tickets}
    poi_ids = {p["id"] for p in POIS}
    assert len(tickets) == 80 and len(ids) == 80
    assert len({t["code"] for t in tickets}) == 80
    assert all(t["demo"] for t in tickets) and all(e["demo"] for e in events)
    assert all(start <= t["created_at"] <= NOW for t in tickets)
    assert all(start <= e["ts"] <= NOW for e in events)
    assert all(e["ticket_id"] in ids and e["poi_id"] in poi_ids for e in events)
    assert all(e["type"] in ("listen", "enter", "exit") for e in events)
    assert events == sorted(events, key=lambda e: e["ts"])
    assert len({e["id"] for e in events}) == len(events)
    # sự kiện không trước lúc vé được mua
    created = {t["id"]: t["created_at"] for t in tickets}
    assert all(e["ts"] >= created[e["ticket_id"]] for e in events)


def test_unused_tickets_have_no_events_and_expire_at_vn_midnight():
    tickets, events = generate_demo(POIS, NOW, n_tickets=200, n_live=10)
    with_events = {e["ticket_id"] for e in events}
    unused = [t for t in tickets if t["device_id"] is None]
    assert unused and all(t["id"] not in with_events for t in unused)
    assert all(t["expires_at"] == datetime(2026, 10, 23, 23, 59, 59, tzinfo=VN_TZ) for t in tickets)


def test_dashboard_has_meaningful_numbers():
    tickets, events = generate_demo(POIS, NOW)
    es, ts = _stores(tickets, events)
    dash = run(stats.build_dashboard(es, ts, POIS, NOW, load_settings()))
    ov, pois, hourly = dash["overview"], dash["pois"], dash["hourly"]

    assert ov["tickets_sold_today"] == 80
    assert 0 < ov["active_tickets"] <= 80
    assert pois["present_total"] > 0
    assert sum(r["passes_today"] for r in pois["pois"]) > 0
    assert sum(1 for r in pois["pois"] if r["passes_today"] > 0) >= 10  # nhiều điểm có số liệu
    assert hourly["totals"]["events"] == len(events)
    assert hourly["totals"]["tickets_sold"] == 80
    busy_hours = [h for h in hourly["hours"] if h["events"]["total"] > 0]
    assert len(busy_hours) >= 5  # biểu đồ có hình dạng, không dồn vào một giờ
    assert all(h["events"]["total"] == 0 for h in hourly["hours"] if h["hour"] < 7)  # chưa mở cửa


def test_works_early_in_the_morning():
    early = datetime(2026, 10, 23, 0, 10, tzinfo=VN_TZ)
    tickets, events = generate_demo(POIS, early, n_tickets=20, n_live=5)
    start, _ = vn_day_range_utc(early.date())
    assert all(start <= t["created_at"] <= early for t in tickets)
    assert all(start <= e["ts"] <= early for e in events)


def test_requires_pois():
    try:
        generate_demo([], NOW)
    except ValueError:
        return
    raise AssertionError("phải báo lỗi khi không có POI")


def test_delete_demo_leaves_real_data():
    tickets, events = generate_demo(POIS, NOW, n_tickets=10, n_live=2)
    es, ts = _stores(tickets, events)
    ts.add({"id": "real-1", "created_at": NOW})
    run(es.insert({"id": "real-e", "ticket_id": "real-1", "poi_id": "tcv-001", "type": "listen", "ts": NOW}))
    assert run(ts.delete_demo()) == 10
    assert run(es.delete_demo()) == len(events)
    assert list(ts.docs) == ["real-1"] and [d["id"] for d in es.docs] == ["real-e"]
