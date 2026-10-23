# 🦁 Hệ Thống Thuyết Minh Tự Động Đa Ngôn Ngữ - Thảo Cầm Viên Sài Gòn

> **Môn học:** Công Nghệ Phần Mềm  
> **Đề tài:** Thuyết minh tự động đa ngôn ngữ  
> **Hướng chọn:** Hướng 3 - BE Dev: Tạo các services giao tiếp với nhau bao gồm CI/CD

---

## 📖 Giới Thiệu Dự Án

Hệ thống cung cấp thuyết minh âm thanh tự động đa ngôn ngữ cho du khách tham quan **Thảo Cầm Viên Sài Gòn**. Khi du khách đến gần một địa điểm, ứng dụng sẽ tự động phát âm thanh giới thiệu bằng ngôn ngữ họ chọn (Việt, Anh, Trung, Nhật, Hàn).

Dự án áp dụng kiến trúc **Microservices** - chia hệ thống thành 3 service nhỏ độc lập, giao tiếp với nhau qua HTTP.

---

## 🏗️ Kiến Trúc Hệ Thống

```
Du khách (Mobile App)
        │
        ▼
┌──────────────────────────────────────────────┐
│            Docker Network (nội bộ)           │
│                                              │
│  ┌─────────────┐   ┌──────────────────┐     │
│  │ Auth Service│   │ Content Service  │     │
│  │  Port 8001  │◄──│    Port 8002     │     │
│  │             │   │                  │     │
│  │ - Đăng ký   │   │ - Danh sách POI  │     │
│  │ - Đăng nhập │   │ - Tìm gần GPS    │     │
│  │ - JWT Token │   │ - CRUD địa điểm  │     │
│  └──────┬──────┘   └────────┬─────────┘     │
│         │ xác minh token    │ lấy nội dung   │
│         └──────────┐        │               │
│                    ▼        ▼               │
│              ┌─────────────────┐            │
│              │  Audio Service  │            │
│              │    Port 8003    │            │
│              │                 │            │
│              │ - TTS đa ngôn ngữ│           │
│              │ - Tải file MP3  │            │
│              └─────────────────┘            │
└──────────────────────────────────────────────┘
```

**Luồng giao tiếp giữa các service:**
1. **Content Service** → gọi **Auth Service** để xác minh token khi cần quyền admin
2. **Audio Service** → gọi **Content Service** để lấy nội dung thuyết minh
3. **Audio Service** → gọi **Auth Service** để xác minh token (endpoint bảo vệ)
4. Ba service chạy trong cùng 1 Docker network, gọi nhau bằng tên container

---

## 👥 Phân Công Công Việc

| Thành viên | Service phụ trách | Chức năng |
|---|---|---|
| **Thành viên A** | 🔐 Auth Service (8001) | Đăng ký, đăng nhập, JWT token |
| **Thành viên B** | 🗺️ Content Service (8002) + 🎙️ Audio Service (8003) | Quản lý POI + TTS đa ngôn ngữ |

---

## 📁 Cấu Trúc Project

```
zoo-narration/
├── .github/
│   └── workflows/
│       └── ci-cd.yml          ← CI/CD GitHub Actions
├── service-auth/
│   ├── main.py                ← Code chính Auth Service
│   ├── test_auth.py           ← Test tự động Auth
│   ├── requirements.txt       ← Thư viện Python cần dùng
│   └── Dockerfile             ← Cách đóng gói container
├── service-content/
│   ├── main.py                ← Code chính Content Service (POI + /events + /stats)
│   ├── events_core.py         ← Cấu hình, giờ VN, Haversine, chống trùng, rate limit
│   ├── event_store.py         ← Lưu events / đọc tickets (Mongo + bộ nhớ)
│   ├── event_service.py       ← Ghi sự kiện: kiểm tra GPS, chống trùng
│   ├── stats.py               ← Định nghĩa và phép tính thống kê
│   ├── seed_demo.py           ← Nạp vé + sự kiện mẫu cho dashboard
│   ├── test_content.py        ← Test POI
│   ├── test_events_logic.py   ← Test số liệu, ranh giới N phút / ngày VN
│   ├── test_events_api.py     ← Test API /events, /stats
│   ├── test_seed_demo.py      ← Test bộ sinh dữ liệu demo
│   ├── requirements.txt
│   └── Dockerfile
├── service-audio/
│   ├── main.py                ← Code chính Audio Service
│   ├── requirements.txt
│   └── Dockerfile
└── docker-compose.yml         ← Chạy tất cả service cùng nhau
```

---

## 🛠️ Công Nghệ Sử Dụng

| Công nghệ | Dùng để làm gì |
|-----------|----------------|
| **Python + FastAPI** | Viết API backend nhanh, tự generate docs |
| **JWT (JSON Web Token)** | Xác thực người dùng không cần session |
| **bcrypt** | Mã hóa mật khẩu an toàn |
| **edge-tts** | Tạo giọng đọc từ Microsoft, miễn phí |
| **httpx** | Gọi HTTP từ service này sang service khác |
| **Docker** | Đóng gói từng service vào container |
| **Docker Compose** | Chạy nhiều container cùng lúc |
| **GitHub Actions** | Tự động test & build khi push code |
| **Pytest** | Framework viết test tự động |

---

## 🚀 Cách Chạy Dự Án

### Cách 1: Chạy từng service riêng (để học/debug)

```bash
# === AUTH SERVICE ===
cd service-auth
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Mở tab terminal mới
# === CONTENT SERVICE ===
cd service-content
pip install -r requirements.txt
uvicorn main:app --reload --port 8002

# Mở tab terminal mới
# === AUDIO SERVICE ===
cd service-audio
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

### Cách 2: Chạy tất cả bằng Docker Compose (khuyên dùng)

```bash
# Đứng ở thư mục gốc zoo-narration/
docker-compose up --build

# Dừng tất cả
docker-compose down
```

---

## 📡 Các API Endpoint

### 🔐 Auth Service (port 8001)

| Method | Endpoint | Mô tả | Cần đăng nhập? |
|--------|----------|-------|----------------|
| GET | `/` | Kiểm tra service | Không |
| GET | `/health` | Health check | Không |
| POST | `/register` | Đăng ký tài khoản | Không |
| POST | `/login` | Đăng nhập, nhận token | Không |
| GET | `/verify` | Kiểm tra token hợp lệ | Có (Token) |
| GET | `/me` | Xem thông tin cá nhân | Có (Token) |

**Ví dụ đăng nhập:**
```bash
curl -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "123456"}'
```

### 🗺️ Content Service (port 8002)

| Method | Endpoint | Mô tả | Quyền |
|--------|----------|-------|-------|
| GET | `/pois` | Danh sách điểm (lọc `?category=`) | Công khai |
| GET | `/pois/{id}` | Chi tiết 1 điểm (đủ bản dịch) | Công khai |
| GET | `/pois/nearby?lat=&lon=&search_radius_m=` | Điểm gần GPS, sắp xếp gần đến xa, kèm `distance_m` | Công khai |
| POST | `/pois` | Thêm điểm, tự sinh audio các ngôn ngữ có mô tả | Admin |
| PUT | `/pois/{id}` | Sửa điểm; chỉ sinh lại audio ngôn ngữ có nội dung đổi | Admin |
| PATCH | `/pois/{id}/translations/{lang}` | Sửa riêng một bản dịch (`name` / `description`) | Admin |
| DELETE | `/pois/{id}` | Xóa điểm và dọn audio liên quan | Admin |
| GET | `/pois/{id}/audio-status` | Trạng thái audio từng ngôn ngữ | Admin |
| POST | `/events` | Du khách gửi sự kiện `listen` / `enter` / `exit` (kèm `lat`, `lon` tùy chọn) | **Ticket token** |
| GET | `/events?poi_id=&ticket_id=&limit=` | Sự kiện mới nhất trước, `ts` giờ VN | Admin |
| GET | `/stats/overview` | Vé bán hôm nay, vé đang hoạt động | Admin |
| GET | `/stats/pois` | Từng điểm: số người đang ở trong điểm, lượt đi qua hôm nay | Admin |
| GET | `/stats/hourly?date=YYYY-MM-DD` | Chuỗi 24 giờ (giờ VN) để vẽ biểu đồ | Admin |
| GET | `/stats/dashboard` | Gộp 3 báo cáo trên cho hôm nay | Admin |

`category`: `thu_an_co`, `thu_an_thit`, `linh_truong`, `chim`, `bo_sat_luong_cu`, `tien_ich`.
`search_radius_m` (tham số tìm kiếm) khác `radius_m` (vùng kích hoạt riêng của mỗi điểm). Endpoint cũ `/pois/nearby/search?radius_m=` vẫn còn để tương thích.

```bash
curl "http://localhost:8002/pois/nearby?lat=10.78755&lon=106.70528&search_radius_m=100"
```

### 🎙️ Audio Service (port 8003)

| Method | Endpoint | Mô tả | Quyền |
|--------|----------|-------|-------|
| GET | `/audio/poi/{id}?lang=vi` | Trả MP3 của điểm, đúng giọng và đúng bản dịch | **Ticket token** |
| GET | `/audio/preview/{id}?lang=` | Nghe thử | Admin |
| GET | `/audio/status/{id}` | Trạng thái `pending / generating / ready / error` | Admin |
| POST | `/tts`, GET `/audio/download/{file}`, GET `/audio/list` | Công cụ admin | Admin |
| POST | `/internal/generate`, `/internal/warmup`, DELETE `/internal/pois/{id}` | Content Service gọi nội bộ | `X-Internal-Key` |

Audio được sinh sẵn khi lưu POI và khi khởi động (chạy nền). Cache theo MD5 của nội dung + ngôn ngữ + giọng. Nhiều request đồng thời cho cùng điểm và ngôn ngữ chỉ sinh một lần.

---

## 📊 Sự kiện và thống kê (giai đoạn 4)

Collection `events` (Content Service): `ticket_id`, `poi_id`, `type` ∈ {listen, enter, exit}, `ts` (UTC trong DB, API trả giờ VN `+07:00`), cùng `distance_m` / `in_zone` khi app gửi GPS. Index: `(ts)`, `(poi_id, ts)`, `(ticket_id, ts)`. Thời điểm `ts` luôn do máy chủ đặt; tọa độ thô không được lưu.

**`POST /events`**: body `{"poi_id","type","lat?","lon?"}`, cần ticket token.

| Mã | Ý nghĩa |
|---|---|
| 201 | Đã ghi |
| 200 + `deduplicated: true` | Trùng sự kiện ngay trước đó của cùng (vé, điểm), cùng loại, cách < `EVENT_DEDUPE_SECONDS` giây. Không ghi thêm, trả lại sự kiện cũ |
| 404 | POI không tồn tại |
| 422 `out_of_range` | `enter` có GPS nhưng cách điểm > `radius_m` + `GEO_TOLERANCE_M` (Haversine) |
| 422 `still_in_range` | `exit` có GPS nhưng còn cách tâm < `radius_m` − `GEO_TOLERANCE_M` |
| 422 `gps_required` | Chỉ khi `EVENT_REQUIRE_GPS=true` mà `enter`/`exit` thiếu GPS |
| 429 | Vé gửi quá `EVENT_RATE_LIMIT` sự kiện / `EVENT_RATE_WINDOW_SEC` giây (có `Retry-After`) |

`listen` luôn được ghi; nếu GPS cho thấy ngoài vùng thì đánh dấu `in_zone=false` và không tính vào "lượt đi qua" hay "đang ở trong điểm". Không gửi GPS thì không kiểm tra (`in_zone=null`) và vẫn tính.

**Định nghĩa các con số** (N = `N_ACTIVE_MINUTES`, mặc định 10; "hôm nay" = ngày theo giờ VN, từ 00:00:00 đến trước 00:00:00 hôm sau):

| Chỉ số | Định nghĩa |
|---|---|
| Vé bán hôm nay | Số vé có `created_at` trong ngày VN |
| Vé đang hoạt động | Số vé distinct có ít nhất 1 sự kiện (loại nào cũng tính) trong N phút gần nhất; đúng mốc N phút vẫn tính |
| Đang ở trong điểm | Vé đã `enter` mà chưa `exit` (tối đa `PRESENCE_ENTER_TTL_MINUTES` = 120 phút kể từ lần enter, để không đếm "người ma" khi app mất `exit`), **hoặc** có `enter`/`listen` tại điểm trong N phút gần nhất và chưa `exit` sau đó. Mỗi vé chỉ gán vào **một** điểm (điểm có hoạt động gần nhất) để tổng không đếm trùng một người |
| Lượt đi qua điểm hôm nay | Số vé distinct có `listen` hoặc `enter` tại điểm trong ngày VN (không tính sự kiện GPS xác nhận ngoài vùng) |
| Chuỗi theo giờ | 24 mốc 0–23 giờ VN, mỗi giờ có `tickets_sold`, `events` (listen/enter/exit/total), `active_tickets`, `visits` (cặp vé–điểm distinct có listen/enter trong giờ đó) |

Cấu hình qua biến môi trường (xem `.env.example`): `N_ACTIVE_MINUTES`, `PRESENCE_ENTER_TTL_MINUTES`, `EVENT_DEDUPE_SECONDS`, `EVENT_RATE_LIMIT`, `EVENT_RATE_WINDOW_SEC`, `GEO_TOLERANCE_M`, `EVENT_REQUIRE_GPS`. Đổi giá trị rồi `docker compose up -d` lại content-service.

**Dữ liệu demo cho dashboard:**
```bash
docker compose exec content-service python seed_demo.py                      # 80 vé, 12 vé đang tham quan
docker compose exec content-service python seed_demo.py --tickets 150 --live 20
docker compose exec content-service python seed_demo.py --date 2026-10-22    # một ngày cũ
docker compose exec content-service python seed_demo.py --reset-only         # xóa dữ liệu demo
```
Dữ liệu demo gắn `demo: true`, chạy lại sẽ xóa bản cũ và nạp mốc thời gian mới; vé/sự kiện thật không bị đụng tới. Số "đang hoạt động / đang ở trong điểm" chỉ đúng ngay sau khi seed (cửa sổ N phút), nên seed lại ngay trước buổi trình bày.

---

## 🧪 Chạy Test Tự Động

```bash
# Test Auth Service
cd service-auth
pytest test_auth.py -v

# Test Content Service (POI, sự kiện, thống kê, seed demo)
cd service-content
pytest -v
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

Khi bạn **push code lên GitHub**, pipeline tự động chạy:

```
Push code lên GitHub
        │
        ▼
┌─────────────────┐
│   JOB 1: TEST   │
│                 │
│ 1. Cài Python   │
│ 2. Cài thư viện │
│ 3. Check syntax │
│ 4. pytest auth  │
│ 5. pytest content│
└────────┬────────┘
         │ Nếu tất cả PASS
         ▼
┌─────────────────────┐
│  JOB 2: DOCKER BUILD │
│                     │
│ 1. Build auth image  │
│ 2. Build content img │
│ 3. Build audio image │
│ 4. Thông báo xong!  │
└─────────────────────┘
```

Xem kết quả tại: `GitHub repo → Actions tab`

---

## 🌍 Ngôn Ngữ Hỗ Trợ

| Mã ngôn ngữ | Ngôn ngữ | Giọng đọc |
|-------------|---------|-----------| 
| `vi` | Tiếng Việt | vi-VN-HoaiMyNeural |
| `en` | Tiếng Anh | en-US-JennyNeural |
| `zh` | Tiếng Trung | zh-CN-XiaoxiaoNeural |
| `ja` | Tiếng Nhật | ja-JP-NanamiNeural |
| `ko` | Tiếng Hàn | ko-KR-SunHiNeural |

---

## 🦁 Các Địa Điểm Trong Thảo Cầm Viên

20 điểm mẫu (`tcv-001` đến `tcv-020`) nằm trong `seed/pois.json`, mỗi điểm có đủ bản dịch vi/en/zh/ja/ko. Admin và nhóm có thể sửa trực tiếp file này (chỉ nạp điểm chưa tồn tại) hoặc sửa qua API. Nội dung và tọa độ cần đối chiếu thực tế.

---

## 📚 Tài liệu API tự động

FastAPI tự động tạo tài liệu API tương tác:
- Auth Service: http://localhost:8001/docs
- Content Service: http://localhost:8002/docs
- Audio Service: http://localhost:8003/docs
