# Frontend – Thuyết minh tự động đa ngôn ngữ

## Yêu cầu
- Node.js 20+ và npm
- Backend 3 service + MongoDB chạy bằng Docker Compose

## Khởi chạy
1. Từ thư mục `zoo4/`, khởi động backend:
   ```bash
   docker compose up --build
   ```
2. Mở terminal khác:
   ```bash
   cd web
   cp .env.example .env
   npm install
   npm run dev
   ```
3. Mở URL do Vite hiển thị (thường là http://localhost:5173).

Mặc định frontend dùng proxy Vite:
- `/api/auth` → `http://localhost:8001`
- `/api/content` → `http://localhost:8002`
- `/api/audio` → `http://localhost:8003`

Nếu có API gateway/reverse proxy, đặt `VITE_API_BASE_URL` trong file `.env` ở thư mục `zoo4/`; frontend sẽ gọi các đường dẫn `/api/auth`, `/api/content`, `/api/audio` qua base URL đó. `VITE_TILE_URL` có thể đổi nguồn tile bản đồ; mặc định là OpenStreetMap. `VITE_PUBLIC_BASE_URL` dùng để tạo link kích hoạt trong QR. Không commit `.env`.

## Tài khoản demo (chỉ hiển thị trong development)
- admin / admin123
- counter01 / counter123

## Các phần đã triển khai
- Trang du khách: bản đồ và danh sách POI, lọc/tìm kiếm, GPS, nearby, chi tiết POI, 5 lựa chọn ngôn ngữ, khóa/nghe audio theo vé, kích hoạt vé và xác nhận chuyển thiết bị, modal vé của tôi.
- Nội bộ: đăng nhập theo role, tạo vé + QR, danh sách vé tự làm mới, quản lý POI với bản đồ chọn tọa độ và bản dịch, dashboard, quản lý tài khoản.
- Design tokens xanh lá, responsive, trạng thái loading/error/empty, các lớp API tách riêng.

## Cần rà soát sau khi chạy backend
- Kiểm thử các luồng thật với API và chỉnh mapping trường nếu phản hồi thực tế khác schema dự kiến.
- Cập nhật giờ mở cửa và nội dung giới thiệu chính thức; thay ảnh placeholder/ảnh minh họa bằng ảnh được phép sử dụng.
- Kiểm tra CORS/proxy nếu triển khai khác môi trường local.
- Kiểm tra audio/TTS cần Internet; lần đầu tạo audio có thể chậm.
