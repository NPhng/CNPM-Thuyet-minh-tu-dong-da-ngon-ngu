"""
Seed dữ liệu demo cho dashboard: vé + sự kiện mẫu trong ngày (giờ VN).

Chạy khi hệ thống đang chạy (script nằm trong image content-service):
    docker compose exec content-service python seed_demo.py
    docker compose exec content-service python seed_demo.py --tickets 150 --live 20
    docker compose exec content-service python seed_demo.py --date 2026-10-22   # ngày cũ, xem /stats/hourly?date=
    docker compose exec content-service python seed_demo.py --reset-only        # chỉ xóa dữ liệu demo

- Mọi bản ghi demo có `demo: true`; mỗi lần chạy xóa dữ liệu demo cũ rồi nạp lại với mốc thời gian mới
  (chạy lại ngay trước buổi trình bày để số "đang hoạt động / đang ở trong điểm" còn tươi).
  Vé và sự kiện thật (không có cờ demo) không bị đụng tới.
- "Vé đang hoạt động" tính theo N phút gần nhất, nên số liệu live chỉ có ý nghĩa ngay sau khi seed.
- Dữ liệu ghi thẳng vào Mongo, không đi qua POST /events (nên không bị chống trùng/rate limit).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from events_core import VN_TZ, as_utc, load_settings, now_utc, to_vn_iso, vn_date_of, vn_day_range_utc

OPEN_HOUR_VN = 7.5  # 07:30
GEO_TOLERANCE_M = 20.0
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _minutes(m: float) -> timedelta:
    return timedelta(minutes=m)


def generate_demo(
    pois: list[dict],
    now: datetime,
    *,
    n_tickets: int = 80,
    n_live: int = 12,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """
    Sinh (tickets, events) cho ngày VN chứa `now`. Thuần túy, xác định theo `seed`.
    - n_live vé mua 16–40 phút trước `now`, đi lộ trình dài nên còn đang ở trong điểm lúc `now`.
    - Các vé còn lại mua rải từ 07:30, dồn về buổi sáng; ~8% chưa kích hoạt (không có sự kiện).
    - Không có sự kiện hay vé nào sau `now`.
    """
    if not pois:
        raise ValueError("Cần có POI để sinh sự kiện")
    rng = random.Random(seed)
    now = as_utc(now)
    day = vn_date_of(now)
    day_start, _ = vn_day_range_utc(day)
    expires_at = day_start + timedelta(days=1) - timedelta(seconds=1)  # 23:59:59 VN

    open_time = day_start + timedelta(hours=OPEN_HOUR_VN)
    if now - open_time < _minutes(60):  # chạy sớm trước 08:30: nén cả ngày vào [00:00, now]
        open_time = day_start
    latest_regular = min(max(open_time + _minutes(5), now - _minutes(45)), now - _minutes(2))
    latest_regular = max(latest_regular, open_time)

    gate = next((p for p in pois if p["id"] == "tcv-001"), None)
    tickets: list[dict] = []
    events: list[dict] = []

    def new_id() -> str:
        return str(uuid.UUID(int=rng.getrandbits(128), version=4))

    def add_event(ticket_id: str, poi: dict, typ: str, ts: datetime, distance: float, in_zone: bool):
        events.append({
            "id": new_id(), "ticket_id": ticket_id, "poi_id": poi["id"], "type": typ, "ts": ts,
            "distance_m": round(distance, 1), "in_zone": in_zone, "demo": True,
        })

    for i in range(n_tickets):
        live = i < n_live
        if live:
            bought = now - _minutes(rng.uniform(16, 40))
        else:
            span = (latest_regular - open_time).total_seconds()
            bought = open_time + timedelta(seconds=span * rng.triangular(0, 1, 0.3))
        bought = max(bought, day_start)
        unused = (not live) and rng.random() < 0.08

        ticket_id = f"demo-{i:04d}"
        code = "ZCV-DEMO-{:04d}-{}".format(i, "".join(rng.choice(CODE_ALPHABET) for _ in range(4)))
        activated_at: Optional[datetime] = None
        if not unused:
            activated_at = min(bought + _minutes(rng.uniform(0.5, 8)), now - timedelta(seconds=1))
        tickets.append({
            "id": ticket_id,
            "code": code,
            "created_by": "demo-seed",
            "created_at": bought,
            "expires_at": expires_at,
            "device_id": None if unused else f"demo-device-{i:04d}",
            "activated_at": activated_at,
            "token_version": 0 if unused else 1,
            "demo": True,
        })
        if unused:
            continue

        # lộ trình: bắt đầu ở Cổng Chính (nếu có), các điểm sau chọn ngẫu nhiên không lặp
        k = min(len(pois), rng.randint(6, 9) if live else rng.randint(3, 9))
        others = [p for p in pois if p is not gate]
        route = ([gate] if gate else []) + rng.sample(others, k - (1 if gate else 0))
        t = activated_at + _minutes(rng.uniform(1, 4))
        for poi in route:
            if t > now:
                break
            r = float(poi.get("radius_m") or 30)
            add_event(ticket_id, poi, "enter", t, rng.uniform(0.2, 0.9) * r, True)
            last = t
            for _ in range(rng.choice([0, 1, 1, 2])):
                lt = t + _minutes(rng.uniform(0.3, 4))
                if lt <= now:
                    add_event(ticket_id, poi, "listen", lt, rng.uniform(0.1, 0.9) * r, True)
                    last = max(last, lt)
            exit_t = max(t + _minutes(rng.uniform(3, 14)), last + timedelta(seconds=20))
            if exit_t > now:
                break  # đang đứng ở điểm này
            dist = r + rng.uniform(1, 25)
            add_event(ticket_id, poi, "exit", exit_t, dist, dist <= r + GEO_TOLERANCE_M)
            t = exit_t + _minutes(rng.uniform(1, 4))

        # thỉnh thoảng nghe thử từ xa (GPS xác nhận ngoài vùng): không tính lượt đi qua
        if rng.random() < 0.07:
            poi = rng.choice(pois)
            lt = activated_at + (now - activated_at) * rng.random()
            add_event(ticket_id, poi, "listen", lt, rng.uniform(150, 400), False)

    events.sort(key=lambda e: e["ts"])
    return tickets, events


def make_ticket_token(ticket: dict) -> str:
    """JWT vé hợp lệ cho vé demo (dùng thử POST /events trong Swagger)."""
    import jwt

    from jwt_auth import JWT_ALGORITHM, JWT_SECRET

    payload = {
        "type": "ticket",
        "sub": ticket["id"],
        "ticket_id": ticket["id"],
        "device_id": ticket["device_id"],
        "token_version": ticket["token_version"],
        "iat": now_utc(),
        "exp": ticket["expires_at"],
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def _load_pois(db) -> list[dict]:
    fields = {"_id": 0, "id": 1, "name": 1, "category": 1, "lat": 1, "lon": 1, "radius_m": 1}
    pois = await db["pois"].find({}, fields).to_list(length=None)
    if pois:
        return pois
    from poi_store import load_seed_pois  # POI chưa được seed vào DB: dùng file seed

    return [
        {k: p.get(k) for k in ("id", "name", "category", "lat", "lon", "radius_m")} for p in load_seed_pois()
    ]


async def run_seed(args) -> None:
    from motor.motor_asyncio import AsyncIOMotorClient

    import stats
    from event_store import MongoEventStore, MongoTicketStore

    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), tz_aware=True)
    db = client[os.getenv("DB_NAME", "zoo")]
    events, tickets = MongoEventStore(db), MongoTicketStore(db)
    try:
        await events.ensure_indexes()
        removed_t, removed_e = await tickets.delete_demo(), await events.delete_demo()
        print(f"Đã xóa dữ liệu demo cũ: {removed_t} vé, {removed_e} sự kiện.")
        if args.reset_only:
            return

        if args.date:
            day = date.fromisoformat(args.date)
            now = datetime(day.year, day.month, day.day, 17, 30, tzinfo=VN_TZ).astimezone(timezone.utc)
        else:
            now = now_utc()
        pois = await _load_pois(db)
        new_tickets, new_events = generate_demo(
            pois, now, n_tickets=args.tickets, n_live=args.live, seed=args.seed
        )
        await tickets.insert_many(new_tickets)
        await events.insert_many(new_events)
        print(f"Đã nạp {len(new_tickets)} vé và {len(new_events)} sự kiện (ngày {vn_date_of(now)}, mốc 'bây giờ' = {to_vn_iso(now)}).")

        if not args.date:
            settings = load_settings()
            dash = await stats.build_dashboard(events, tickets, pois, now, settings)
            ov = dash["overview"]
            print(f"  Vé bán hôm nay: {ov['tickets_sold_today']}")
            print(f"  Vé đang hoạt động (N={ov['n_active_minutes']} phút): {ov['active_tickets']}")
            print(f"  Đang ở trong các điểm: {dash['pois']['present_total']}")
            top = [r for r in dash["pois"]["pois"] if r["passes_today"]][:5]
            for r in top:
                print(f"  - {r['name']}: đang ở {r['present_now']}, lượt đi qua {r['passes_today']}")
            live = next((t for t in new_tickets if t["device_id"]), None)
            if live:
                print("\nTicket token demo (thử POST /events, Authorize ở Swagger của Content Service):")
                print(make_ticket_token(live))
        else:
            print(f"Xem chuỗi giờ: GET /stats/hourly?date={args.date}")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed vé + sự kiện demo cho dashboard")
    parser.add_argument("--tickets", type=int, default=80, help="tổng số vé demo (mặc định 80)")
    parser.add_argument("--live", type=int, default=12, help="số vé đang tham quan lúc seed (mặc định 12)")
    parser.add_argument("--seed", type=int, default=42, help="seed ngẫu nhiên, cùng seed cho cùng dữ liệu")
    parser.add_argument("--date", help="YYYY-MM-DD: seed cho một ngày đã qua (mốc 17:30 giờ VN)")
    parser.add_argument("--reset-only", action="store_true", help="chỉ xóa dữ liệu demo")
    args = parser.parse_args()
    if args.live > args.tickets:
        parser.error("--live không được lớn hơn --tickets")
    asyncio.run(run_seed(args))


if __name__ == "__main__":
    main()
