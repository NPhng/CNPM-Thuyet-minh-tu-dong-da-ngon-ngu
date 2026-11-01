"""
Thống kê dashboard (giai đoạn 4). Các hàm compute_* là thuần túy, build_* đọc dữ liệu qua store.

ĐỊNH NGHĨA (N = N_ACTIVE_MINUTES, mặc định 10; "hôm nay" = ngày theo giờ VN):

1. Vé bán hôm nay: số vé có created_at trong ngày VN.

2. Vé đang hoạt động: số vé DISTINCT có ít nhất 1 sự kiện (bất kể loại) với
   now - N phút <= ts <= now. Đúng mốc N phút vẫn tính (đóng hai đầu).

3. Số người đang ở trong điểm P. Với mỗi cặp (vé, điểm), duyệt sự kiện theo thời gian:
     - exit  -> xóa trạng thái (không còn ở điểm).
     - enter -> ghi nhớ "đã vào" và "hoạt động gần nhất".
     - listen (không bị đánh dấu ngoài vùng) -> cập nhật "hoạt động gần nhất".
   Vé được tính là đang ở P nếu thỏa MỘT trong hai:
     (a) đã enter, chưa exit sau đó, và lần enter gần nhất cách bây giờ <= PRESENCE_ENTER_TTL_MINUTES
         (mặc định 120 phút; chặn "người ma" khi app không gửi được exit);
     (b) có hoạt động enter/listen tại P trong N phút gần nhất (và chưa exit sau đó) —
         phủ trường hợp app bỏ lỡ enter hoặc người dùng ở lâu chỉ nghe audio.
   Mỗi vé chỉ được gán vào MỘT điểm: điểm có hoạt động gần nhất, để tổng không đếm trùng một người
   khi thiếu exit hoặc hai vùng chồng nhau.

4. Lượt đi qua điểm P hôm nay: số vé DISTINCT có listen hoặc enter tại P trong ngày VN.
   Sự kiện có GPS xác nhận nằm ngoài vùng (in_zone=false) không tính; không có GPS (in_zone=null) vẫn tính.

5. Chuỗi theo giờ: 24 mốc 00..23 giờ VN của một ngày. Mỗi giờ: số vé bán, số sự kiện theo loại,
   số vé hoạt động (distinct trong giờ đó), số lượt ghé (cặp (vé, điểm) distinct có listen/enter
   trong giờ đó — một vé quay lại ở giờ khác được tính lại, nên tổng các giờ >= lượt đi qua cả ngày).

Sự kiện của POI đã bị xóa không nằm trong số liệu từng điểm; vẫn tính vào vé hoạt động và chuỗi theo giờ.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from events_core import (
    EVENT_TYPES,
    VN_TZ,
    Settings,
    as_utc,
    to_vn_iso,
    vn_date_of,
    vn_day_range_utc,
)

VISIT_TYPES = ("listen", "enter")

DEFINITIONS = {
    "tickets_sold_today": "Số vé có created_at trong ngày theo giờ VN.",
    "active_tickets": "Số vé distinct có ít nhất 1 sự kiện trong N phút gần nhất (tính cả mốc đúng N phút).",
    "present_now": (
        "Vé đã enter và chưa exit (tối đa PRESENCE_ENTER_TTL_MINUTES kể từ lần enter), "
        "hoặc có enter/listen tại điểm trong N phút gần nhất và chưa exit sau đó. "
        "Mỗi vé chỉ gán vào điểm có hoạt động gần nhất."
    ),
    "passes_today": "Số vé distinct có listen hoặc enter tại điểm trong ngày VN; bỏ sự kiện có GPS xác nhận ngoài vùng.",
    "hourly": "24 mốc giờ VN; visits = cặp (vé, điểm) distinct có listen/enter trong giờ đó.",
}


def counts_as_visit(event: dict) -> bool:
    """listen/enter và không bị xác nhận là ngoài vùng kích hoạt."""
    return event["type"] in VISIT_TYPES and event.get("in_zone") is not False


# ------------------------------------------------------------ phép tính thuần

def compute_active_tickets(events: Iterable[dict]) -> int:
    return len({e["ticket_id"] for e in events})


def compute_presence(events: Iterable[dict], now: datetime, settings: Settings) -> dict[str, int]:
    """
    events: sự kiện trong [now - TTL, now]. Trả {poi_id: số vé đang ở điểm}.
    Sự kiện sau `now` bị bỏ qua.
    """
    now = as_utc(now)
    n_window = timedelta(minutes=settings.n_active_minutes)
    ttl_window = timedelta(minutes=settings.presence_enter_ttl_minutes)

    # (ticket, poi) -> [enter_ts, last_active_ts]
    state: dict[tuple[str, str], list[Optional[datetime]]] = {}
    for e in sorted(events, key=lambda x: as_utc(x["ts"])):
        ts = as_utc(e["ts"])
        if ts > now:
            continue
        key = (e["ticket_id"], e["poi_id"])
        if e["type"] == "exit":
            state[key] = [None, None]
        elif counts_as_visit(e):
            st = state.setdefault(key, [None, None])
            if e["type"] == "enter":
                st[0] = ts
            st[1] = ts

    best: dict[str, tuple[datetime, str]] = {}  # ticket -> (last_active, poi) của điểm thắng
    for (ticket_id, poi_id), (enter_ts, active_ts) in state.items():
        if active_ts is None:
            continue
        present = (enter_ts is not None and now - enter_ts <= ttl_window) or (now - active_ts <= n_window)
        if not present:
            continue
        cur = best.get(ticket_id)
        # hoạt động mới hơn thắng; bằng nhau thì poi_id nhỏ hơn thắng (kết quả ổn định)
        if cur is None or active_ts > cur[0] or (active_ts == cur[0] and poi_id < cur[1]):
            best[ticket_id] = (active_ts, poi_id)

    counts: dict[str, int] = defaultdict(int)
    for _, poi_id in best.values():
        counts[poi_id] += 1
    return dict(counts)


def compute_passes(day_events: Iterable[dict]) -> dict[str, int]:
    """{poi_id: số vé distinct có listen/enter (trong vùng) tại điểm}."""
    seen: dict[str, set[str]] = defaultdict(set)
    for e in day_events:
        if counts_as_visit(e):
            seen[e["poi_id"]].add(e["ticket_id"])
    return {poi_id: len(tickets) for poi_id, tickets in seen.items()}


def compute_hourly(day_events: Iterable[dict], sold: Iterable[dict]) -> list[dict]:
    """24 phần tử, giờ VN 0..23, điền 0 cho giờ trống."""
    hours = [
        {
            "hour": h,
            "label": f"{h:02d}:00",
            "tickets_sold": 0,
            "events": {**{t: 0 for t in EVENT_TYPES}, "total": 0},
            "active_tickets": 0,
            "visits": 0,
        }
        for h in range(24)
    ]
    active: dict[int, set] = defaultdict(set)
    visits: dict[int, set] = defaultdict(set)
    for e in day_events:
        h = as_utc(e["ts"]).astimezone(VN_TZ).hour
        hours[h]["events"][e["type"]] += 1
        hours[h]["events"]["total"] += 1
        active[h].add(e["ticket_id"])
        if counts_as_visit(e):
            visits[h].add((e["ticket_id"], e["poi_id"]))
    for t in sold:
        hours[as_utc(t["created_at"]).astimezone(VN_TZ).hour]["tickets_sold"] += 1
    for h in range(24):
        hours[h]["active_tickets"] = len(active[h])
        hours[h]["visits"] = len(visits[h])
    return hours


# ------------------------------------------------------------ đọc dữ liệu + ghép

def _day_info(day: date) -> dict:
    start, end = vn_day_range_utc(day)
    return {"date": day.isoformat(), "start": to_vn_iso(start), "end": to_vn_iso(end), "timezone": "Asia/Ho_Chi_Minh"}


async def build_overview(events_store, tickets_store, now: datetime, settings: Settings) -> dict:
    now = as_utc(now)
    day = vn_date_of(now)
    start, end = vn_day_range_utc(day)
    window_start = now - timedelta(minutes=settings.n_active_minutes)
    sold = await tickets_store.created_between(start, end)
    window_events = await events_store.find_range(window_start, now, end_inclusive=True)
    return {
        "generated_at": to_vn_iso(now),
        "day": _day_info(day),
        "n_active_minutes": settings.n_active_minutes,
        "active_window": {"from": to_vn_iso(window_start), "to": to_vn_iso(now)},
        "tickets_sold_today": len(sold),
        "active_tickets": compute_active_tickets(window_events),
        "definition": {k: DEFINITIONS[k] for k in ("tickets_sold_today", "active_tickets")},
    }


async def build_pois(
    events_store,
    pois: list[dict],
    now: datetime,
    settings: Settings,
    day_events: Optional[list[dict]] = None,
) -> dict:
    now = as_utc(now)
    day = vn_date_of(now)
    start, end = vn_day_range_utc(day)
    if day_events is None:
        day_events = await events_store.find_range(start, end)
    known = {p["id"] for p in pois}

    lookback = now - timedelta(minutes=settings.presence_enter_ttl_minutes)
    recent = await events_store.find_range(lookback, now, end_inclusive=True)
    presence = compute_presence([e for e in recent if e["poi_id"] in known], now, settings)
    passes = compute_passes(e for e in day_events if e["poi_id"] in known)

    rows = [
        {
            "poi_id": p["id"],
            "name": p.get("name") or p["id"],
            "category": p.get("category"),
            "present_now": presence.get(p["id"], 0),
            "passes_today": passes.get(p["id"], 0),
        }
        for p in pois
    ]
    rows.sort(key=lambda r: (-r["present_now"], -r["passes_today"], r["poi_id"]))
    return {
        "generated_at": to_vn_iso(now),
        "day": _day_info(day),
        "n_active_minutes": settings.n_active_minutes,
        "presence_enter_ttl_minutes": settings.presence_enter_ttl_minutes,
        "present_total": sum(presence.get(p["id"], 0) for p in pois),
        "pois": rows,
        "definition": {k: DEFINITIONS[k] for k in ("present_now", "passes_today")},
    }


async def build_hourly(
    events_store,
    tickets_store,
    day: date,
    day_events: Optional[list[dict]] = None,
) -> dict:
    start, end = vn_day_range_utc(day)
    if day_events is None:
        day_events = await events_store.find_range(start, end)
    sold = await tickets_store.created_between(start, end)
    hours = compute_hourly(day_events, sold)
    return {
        "day": _day_info(day),
        "hours": hours,
        "totals": {
            "tickets_sold": sum(h["tickets_sold"] for h in hours),
            "events": sum(h["events"]["total"] for h in hours),
        },
        "definition": {"hourly": DEFINITIONS["hourly"]},
    }


async def build_dashboard(events_store, tickets_store, pois: list[dict], now: datetime, settings: Settings) -> dict:
    """Gộp 3 báo cáo cho hôm nay, đọc sự kiện trong ngày một lần."""
    now = as_utc(now)
    day = vn_date_of(now)
    start, end = vn_day_range_utc(day)
    day_events = await events_store.find_range(start, end)
    return {
        "overview": await build_overview(events_store, tickets_store, now, settings),
        "pois": await build_pois(events_store, pois, now, settings, day_events=day_events),
        "hourly": await build_hourly(events_store, tickets_store, day, day_events=day_events),
    }
