## 1. Chuẩn bị (làm 1 lần)
- Cài **Docker Desktop**, mở lên và chờ biểu tượng cá voi báo "running".
- Máy phải có Internet (Audio Service gọi Microsoft Edge TTS).

## 2. Chạy hệ thống
Mở terminal (PowerShell) **trong thư mục `zoo4`** (thư mục có file `docker-compose.yml`), chạy:
```bash
docker compose up --build
```
Lần đầu build mất vài phút. Khi thấy log của cả 3 service và `docker compose ps` (mở terminal thứ hai) báo `healthy` là xong.

| Service | Swagger UI (trang để bấm thử API) |
|---|---|
| Auth    | http://localhost:8001/docs |
| Content | http://localhost:8002/docs |
| Audio   | http://localhost:8003/docs |

Tắt hệ thống: `Ctrl+C`, rồi `docker compose down` (KHÔNG thêm `-v`, để giữ các file MP3 đã tạo).

## 3. Cách dùng Swagger
Bấm vào một API -> **Try it out** -> điền ô -> **Execute** -> xem kết quả ở mục Response.

**Gửi token:** bấm nút **Authorize** ở góc trên bên phải trang Swagger, dán token (không cần gõ `Bearer`) rồi Authorize. Mỗi trang 8001/8002/8003 có Authorize riêng. Đổi giữa admin và du khách thì Authorize lại bằng token khác.
- **Token admin** (`POST /login`): dùng cho CRUD POI, sửa bản dịch, nghe thử, xem trạng thái audio.
- **Ticket token** (`POST /tickets/activate`): dùng cho du khách nghe audio. Đọc POI (danh sách, chi tiết, nearby) **không cần token**.

## 4. Kịch bản demo

| Bước | Việc làm | Trang | Kết quả cần thấy |
|---|---|---|---|
| 1 | **Đăng nhập admin**: `POST /login` với `{"username":"admin","password":"admin123"}` | Auth (8001) | Copy `token` làm **token admin**. |
| 2 | **Đăng nhập quầy vé**: `POST /login` với `counter01` / `counter123`, Authorize bằng token đó, rồi `POST /tickets` | Auth (8001) | Nhận `code` của vé. |
| 3 | **Du khách kích hoạt vé**: `POST /tickets/activate` với `{"code":"<code>","device_id":"demo-device-0001"}` | Auth (8001) | Copy `ticket_token`. |
| 4 | **Xem điểm (không cần vé)**: `GET /pois`, `GET /pois/tcv-001`, `GET /pois?category=chim` | Content (8002) | 20 điểm, mỗi điểm có `translations` đủ vi/en/zh/ja/ko. |
| 5 | **Tìm gần GPS**: `GET /pois/nearby` với `lat=10.78755`, `lon=106.70528`, `search_radius_m=150` | Content (8002) | Sắp xếp gần đến xa; Cổng Chính `distance_m` = 0, `within_poi_radius` = true. `search_radius_m` là bán kính tìm, còn `radius_m` là vùng kích hoạt riêng của từng điểm. |
| 6 | **Nghe thuyết minh**: `GET /audio/poi/tcv-001` với `lang=ja`, Authorize bằng **ticket token** | Audio (8003) | Nhận file MP3 giọng Nhật đọc bản dịch tiếng Nhật. Thử `vi`, `en`, `zh`, `ko`. Không có vé thì 401. |
| 7 | **Sửa một bản dịch**: `PATCH /pois/tcv-001/translations/en` với token admin, body `{"description":"A new English description."}` | Content (8002) | 200, `audio_status.en` = `pending`. |
| 8 | **Xem trạng thái audio**: `GET /audio/status/tcv-001` với token admin (đợi vài giây) | Audio (8003) | `en` chuyển `generating` rồi `ready`. Nghe thử: `GET /audio/preview/tcv-001?lang=en`. |
| 9 | **Thêm / xóa điểm**: `POST /pois` với token admin (mẫu trong Swagger), rồi `DELETE /pois/{id}` | Content (8002) | 201 rồi 200. Token quầy vé thì 403, không token thì 401. File audio của điểm bị xóa cũng được dọn. |

### Sự kiện và thống kê (giai đoạn 4)

| Bước | Việc làm | Trang | Kết quả cần thấy |
|---|---|---|---|
| 10 | **Nạp dữ liệu demo**: `docker compose exec content-service python seed_demo.py` | Terminal | In số vé, số vé đang hoạt động, các điểm đông nhất và một ticket token demo. |
| 11 | **Xem thống kê**: Authorize bằng token admin, gọi `GET /stats/dashboard` (hoặc `/stats/overview`, `/stats/pois`, `/stats/hourly`) | Content (8002) | Vé bán hôm nay, vé đang hoạt động, mỗi điểm có `present_now` và `passes_today`, 24 mốc giờ VN. |
| 12 | **Gửi sự kiện**: Authorize bằng ticket token (từ bước 3 hoặc do seed in ra), `POST /events` với `{"poi_id":"tcv-001","type":"enter","lat":10.78755,"lon":106.70528}` | Content (8002) | 201, `ts` giờ `+07:00`. Gửi lại ngay: 200 với `deduplicated: true`. |
| 13 | **Thử chặn sai vị trí**: `POST /events` với `type=enter`, `lat=10.79`, `lon=106.70528` | Content (8002) | 422 `out_of_range`. |
| 14 | **Xem số đổi**: gọi lại `GET /stats/pois` | Content (8002) | `present_now` và `passes_today` của Cổng Chính tăng. Sau hơn N phút không có sự kiện mới, vé rời danh sách "đang hoạt động". |

`GET /events?ticket_id=...` (admin) liệt kê sự kiện mới nhất trước để đối chiếu. Đổi N bằng biến `N_ACTIVE_MINUTES` (mặc định 10 phút).

Lưu ý:
- Lần chạy đầu, Content Service tự seed 20 điểm từ `seed/pois.json` rồi **sinh sẵn audio ở chế độ nền** (5 ngôn ngữ x 20 điểm, mất vài phút, cần Internet). Hệ thống vẫn dùng được trong lúc đó; điểm nào chưa có file sẽ được sinh ngay khi có người yêu cầu.
- Bước 6 và 8 cần Internet vì Audio Service gọi Microsoft Edge TTS. Nếu ra 502, kiểm tra mạng rồi thử lại.

## 5. Chạy test
```bash
cd service-auth    && pip install -r requirements.txt pytest httpx && pytest -v
cd service-content && pip install -r requirements.txt pytest httpx && pytest -v
cd service-audio   && pip install -r requirements.txt pytest httpx && AUDIO_DIR=/tmp/audio_files pytest -v
```

## 6. Dữ liệu và seed
- Mỗi service có MongoDB riêng: auth (`mongo_auth_data`: users, tickets), content (`mongo_content_data`: pois, events), audio (`mongo_audio_data`: audio_tracks). MP3 lưu ở volume `audio_files`. `docker compose down` giữ nguyên dữ liệu; `docker compose down -v` xóa sạch.
- Dữ liệu mẫu nằm ở `seed/pois.json` (20 điểm, 5 ngôn ngữ). Seed chỉ **thêm điểm có `id` chưa tồn tại**, không ghi đè điểm đã có. Muốn nạp lại sau khi sửa file: sửa điểm bằng API admin, hoặc `docker compose down -v`.
- Tọa độ, tên khu và nội dung mô tả trong seed do AI soạn, cần đối chiếu thực tế với Thảo Cầm Viên; bản dịch zh/ja/ko nên nhờ người biết ngôn ngữ đó đọc lại.