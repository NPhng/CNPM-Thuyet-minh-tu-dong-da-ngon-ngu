
# Thuyết minh tự động đa ngôn ngữ – Thảo Cầm Viên

Ứng dụng hỗ trợ khách tham quan tra cứu các điểm tham quan trên bản đồ và nghe nội dung thuyết minh bằng nhiều ngôn ngữ. Hệ thống sử dụng vé điện tử để cấp quyền nghe audio; nhân viên có thể quản lý vé, điểm tham quan, nội dung dịch và theo dõi thống kê hoạt động.

## Thành viên nhóm

Đồ án môn Công nghệ Phần mềm - Khoa Công nghệ Thông tin, Trường Đại học Sài Gòn.

| STT | Họ và tên | MSSV |
|---|---|---|
| 1 | Trần Công Minh Trang | 3124411318 |
| 2 | Đặng Huỳnh Ngọc Phượng | 3124411243 | 

**Giảng viên:** Nguyễn Quốc Huy

## 1. Tính năng chính

### Dành cho khách tham quan
- Xem bản đồ và danh sách các điểm tham quan .
- Tìm kiếm, lọc theo danh mục và xem thông tin chi tiết từng điểm.
- Sử dụng GPS để tìm các điểm ở gần.
- Chọn một trong 5 ngôn ngữ: Tiếng Việt, English, 中文, 日本語, 한국어.
- Kích hoạt vé bằng mã/QR để mở quyền nghe thuyết minh.
- Phát audio thuyết minh tương ứng với ngôn ngữ đã chọn.

### Dành cho nhân viên và quản trị viên
- Đăng nhập theo vai trò nhân viên quầy vé  hoặc quản trị viên .
- Tạo vé và mã QR; quản lý danh sách vé.
- Quản lý POI, tọa độ, bán kính và nội dung bản dịch.
- Tự động tạo lại audio khi nội dung dịch thay đổi.
- Theo dõi trạng thái tạo audio và nghe thử bản audio.
- Xem dashboard, thống kê vé và lượt hoạt động tại các POI.
- Quản lý tài khoản nhân viên.

## 2. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Frontend | React, TypeScript, Vite, React Router |
| Giao diện bản đồ | Leaflet, React Leaflet, OpenStreetMap |
| Biểu đồ | Recharts |
| Backend API | Python, FastAPI |
| Cơ sở dữ liệu | MongoDB 7 |
| Xác thực | JWT, bcrypt |
| Chuyển văn bản thành giọng nói | Microsoft Edge TTS (edge-tts) |
| Dịch nội dung | Translator, Gemini API và MyMemory |
| Đóng gói môi trường | Docker, Docker Compose |
| Kiểm thử và CI/CD | pytest, GitHub Actions |

## 3. Kiến trúc hệ thống

Backend được chia thành 3 microservice. Mỗi service sở hữu một MongoDB riêng; các service không truy cập trực tiếp database của nhau.

```text
                    ┌──────────────────────┐
                    │   React Web (Vite)   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
        ┌─────▼─────┐    ┌─────▼──────┐   ┌─────▼─────┐
        │ Auth API  │    │ Content API│   │ Audio API │
        │   :8001   │    │   :8002    │   │   :8003   │
        └─────┬─────┘    └─────┬──────┘   └─────┬─────┘
              │                │                │
        ┌─────▼─────┐    ┌─────▼──────┐   ┌─────▼─────┐
        │ Mongo Auth│    │MongoContent│   │ MongoAudio│
        │   :27018  │    │   :27019   │   │   :27020  │
        └───────────┘    └────────────┘   └───────────┘
```

### Các thành phần

- **Auth Service (service-auth):** Đăng nhập nhân viên, cấp JWT, tạo/quản lý vé, kích hoạt vé cho khách và cung cấp API nội bộ để service khác xác minh vé.

- **Content Service (service-content):** Quản lý POI, bản dịch, tìm POI theo vị trí, tiếp nhận sự kiện vào/ra/nghe và cung cấp thống kê.

- **Audio Service (service-audio):** Tạo và lưu file MP3 theo ngôn ngữ, quản lý trạng thái audio và kiểm tra quyền nghe.

- **Web (web):** Giao diện khách tham quan và khu vực quản trị/nhân viên.

## 4. Cấu trúc thư mục

```text
CNPM-Thuyet-minh-tu-dong-da-ngon-ngu/
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml
│
├── PRD/
│   ├── .keep
│   └── Product Requirements Document.pdf
│
├── source/
│   ├── .env.example
│   ├── DEMO.md
│   ├── docker-compose.yml
│   ├── package-lock.json
│   ├── start-ngrok.sh
│   │
│   ├── seed/
│   │   └── pois.json
│   │
│   ├── service-audio/
│   │   ├── auth_client.py
│   │   ├── Dockerfile
│   │   ├── jwt_auth.py
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── test_audio.py
│   │
│   ├── service-auth/
│   │   ├── Dockerfile
│   │   ├── jwt_auth.py
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   ├── seed_users.py
│   │   ├── test_auth.py
│   │   └── tickets.py
│   │
│   ├── service-content/
│   │   ├── audio_client.py
│   │   ├── auth_client.py
│   │   ├── Dockerfile
│   │   ├── event_service.py
│   │   ├── event_store.py
│   │   ├── events_core.py
│   │   ├── jwt_auth.py
│   │   ├── main.py
│   │   ├── poi_store.py
│   │   ├── requirements.txt
│   │   ├── seed_demo.py
│   │   ├── stats.py
│   │   ├── test_content.py
│   │   ├── test_events_api.py
│   │   ├── test_events_logic.py
│   │   ├── test_seed_demo.py
│   │   ├── test_translate.py
│   │   └── translator.py
│   │
│   └── web/
│       ├── .env.example
│       ├── index.html
│       ├── package-lock.json
│       ├── package.json
│       ├── postcss.config.js
│       ├── README.md
│       ├── tailwind.config.js
│       ├── tsconfig.json
│       ├── vite.config.ts
│       │
│       ├── public/
│       │   └── images/
│       │       ├── tcv-001.jpg
│       │       ├── tcv-002.jpg
│       │       ├── ...
│       │       └── tcv-020.jpg
│       │
│       └── src/
│           ├── api/
│           │   └── client.ts
│           ├── App.tsx
│           ├── i18n.ts
│           ├── main.tsx
│           ├── style.css
│           ├── useLang.ts
│           └── vite-env.d.ts
│
├── .gitignore
└── README.md
```

### Mô tả các thư mục chính

| Thư mục | Chức năng |
|---|---|
| `.github/workflows/` | Chứa cấu hình CI/CD bằng GitHub Actions |
| `PRD/` | Chứa tài liệu đặc tả yêu cầu sản phẩm |
| `source/seed/` | Chứa dữ liệu mẫu các điểm tham quan |
| `source/service-auth/` | Xử lý xác thực, tài khoản và quản lý vé |
| `source/service-content/` | Quản lý POI, bản dịch, sự kiện và thống kê |
| `source/service-audio/` | Xử lý chuyển văn bản thành giọng nói và quản lý audio |
| `source/web/` | Chứa mã nguồn giao diện người dùng React |
| `source/web/public/images/` | Chứa hình ảnh các điểm tham quan |
| `source/web/src/` | Chứa mã nguồn frontend |

## 5. Cài đặt và chạy dự án

### Lấy mã nguồn

```bash
git clone <repository-url>
cd CNPM-Thuyet-minh-tu-dong-da-ngon-ngu-main
```


### Cấu hình backend

```bash
cd source
cp .env.example .env
```

Mở file `source/.env` và thiết lập các giá trị bí mật.

Có thể tạo chuỗi ngẫu nhiên bằng Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Điền tối thiểu các biến sau:

```env
JWT_SECRET=<chuỗi-ngẫu-nhiên-tối-thiểu-32-ký-tự>
INTERNAL_SERVICE_KEY=<chuỗi-ngẫu-nhiên-tối-thiểu-16-ký-tự>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<mật-khẩu-admin-riêng>
COUNTER_USERNAME=counter01
COUNTER_PASSWORD=<mật-khẩu-quầy-vé-riêng>
```

### Khởi động backend

Vẫn tại thư mục `source/`, chạy:

```bash
docker compose up --build
```

Các API mặc định:

| Service | URL | Swagger |
|---|---|---|
| Auth | http://localhost:8001 | http://localhost:8001/docs |
| Content | http://localhost:8002 | http://localhost:8002/docs |
| Audio | http://localhost:8003 | http://localhost:8003/docs |

MongoDB được ánh xạ ra máy local tại các cổng `27018`, `27019`, `27020`. Các service giao tiếp với nhau qua mạng Docker nội bộ.

### Khởi động frontend

Mở terminal mới:

```bash
cd source/web
cp .env.example .env
npm install
npm run dev
```

Truy cập địa chỉ Vite hiển thị trên terminal là:

```text
http://localhost:5173
```

Trong môi trường phát triển, Vite proxy các đường dẫn:

- `/api/auth` → Auth Service `http://localhost:8001`
- `/api/content` → Content Service `http://localhost:8002`
- `/api/audio` → Audio Service `http://localhost:8003`

## 6. Tài khoản và xác thực

Hệ thống hỗ trợ hai vai trò tài khoản:

- **Admin:** Quản trị viên, có quyền quản lý hệ thống.
- **Counter:** Nhân viên quầy vé, có quyền thực hiện các thao tác liên quan đến vé.

Thông tin đăng nhập được cấu hình thông qua file `.env`.

## 7. Dữ liệu mẫu và cơ sở dữ liệu

### Database-per-Service

| MongoDB | Cổng local | Database mặc định | Dữ liệu |
|---|---:|---|---|
| Auth | 27018 | `zoo_auth` | users, tickets |
| Content | 27019 | `zoo_content` | pois, events |
| Audio | 27020 | `zoo_audio` | audio_tracks |

File MP3 được lưu trong Docker volume `audio_files`.

### Quản lý dữ liệu Docker

Dừng container nhưng giữ dữ liệu:

```bash
docker compose down
```

Dừng và xóa toàn bộ dữ liệu volume:

```bash
docker compose down -v
```

### 8. CI/CD với GitHub Actions

Workflow được cấu hình tại:

```text
.github/workflows/ci-cd.yml
```

Pipeline gồm 4 công việc chính:

1. **Backend Tests:** Tự động chạy pytest cho 3 backend service.
2. **Frontend Build:** Cài đặt dependencies và build ứng dụng React/Vite.
3. **Docker Compose Validation:** Kiểm tra khả năng build các Docker service.
4. **Publish Docker Images:** Build và đẩy Docker images lên GitHub Container Registry (GHCR) khi push code lên nhánh `main`.

