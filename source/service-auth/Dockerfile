"""
Dockerfile cho Auth Service
============================
Dockerfile là "công thức" để Docker đóng gói ứng dụng vào 1 container.
Giống như đóng gói cả môi trường Python vào 1 hộp, chạy ở đâu cũng được.

Các bước:
1. Lấy image Python 3.11 (hệ điều hành thu nhỏ có sẵn Python)
2. Copy code vào trong container
3. Cài thư viện từ requirements.txt
4. Chạy ứng dụng bằng uvicorn
"""
# Dùng Python 3.11, bản "slim" để nhẹ hơn
FROM python:3.11-slim

# Cài curl cho Docker healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Thư mục làm việc bên trong container
WORKDIR /app

# Copy file requirements trước (để Docker cache lại, không cài lại mỗi lần)
COPY requirements.txt .

# Cài các thư viện Python cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code vào container
COPY . .

# Mở cổng 8001 (auth service chạy ở cổng này)
EXPOSE 8001

# Lệnh chạy khi container khởi động
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
