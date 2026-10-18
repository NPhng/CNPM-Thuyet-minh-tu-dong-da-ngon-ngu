import pytest
from fastapi.testclient import TestClient  # Dùng để test FastAPI mà không cần chạy server thật
from main import app, fake_users_db        # Import ứng dụng và database

# Tạo client để gọi API trong test
client = TestClient(app)

# Hàm chạy trước/sau mỗi test
@pytest.fixture(autouse=True)
def clear_database():
    fake_users_db.clear()  # Xóa hết user cũ
    yield                   # Cho test chạy
    fake_users_db.clear()  # Xóa lại sau test


# Test 1: Kiểm tra service có chạy không
def test_service_root():
    response = client.get("/")
    assert response.status_code == 200           
    data = response.json()
    assert data["service"] == "Auth Service"     # Đúng tên service
    assert data["status"] == "đang chạy"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# Test 2: Đăng ký tài khoản
def test_register_success():
    response = client.post("/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Người Dùng Test"
    })
    assert response.status_code == 200
    data = response.json()

    # Kiểm tra các field trả về
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "token" in data          # Phải có token
    assert len(data["token"]) > 0   # Token không được rỗng
    assert "user_id" in data        # Phải có user_id


def test_register_duplicate_username():
    # Đăng ký lần 1
    client.post("/register", json={
        "username": "nguoidung",
        "email": "a@test.com",
        "password": "pass123"
    })

    # Đăng ký lần 2 cùng username → phải lỗi
    response = client.post("/register", json={
        "username": "nguoidung",  # Username trùng!
        "email": "b@test.com",
        "password": "pass456"
    })
    assert response.status_code == 400   # HTTP 400 = lỗi client
    assert "đã được sử dụng" in response.json()["detail"]


# Test 3: Đăng nhập
def test_login_success():
    # Đăng ký trước
    client.post("/register", json={
        "username": "phuong",
        "email": "phuong@test.com",
        "password": "matkhau123"
    })

    # Đăng nhập
    response = client.post("/login", json={
        "username": "phuong",
        "password": "matkhau123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "phuong"
    assert "token" in data


def test_login_wrong_password():
    client.post("/register", json={
        "username": "testuser2",
        "email": "test2@test.com",
        "password": "matkhaudung"
    })

    response = client.post("/login", json={
        "username": "testuser2",
        "password": "matkhausai"  # Sai mật khẩu!
    })
    assert response.status_code == 401   # HTTP 401 = không có quyền


def test_login_user_not_found():
    response = client.post("/login", json={
        "username": "khongtontai",
        "password": "batkymatkhau"
    })
    assert response.status_code == 401


# Test 4: Verify Token
def test_verify_valid_token():
    # Đăng ký và lấy token
    response = client.post("/register", json={
        "username": "tokentest",
        "email": "token@test.com",
        "password": "pass123"
    })
    token = response.json()["token"]

    # Kiểm tra token
    verify_response = client.get(
        "/verify",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] == True
    assert verify_response.json()["username"] == "tokentest"


def test_verify_invalid_token():
    response = client.get(
        "/verify",
        headers={"Authorization": "Bearer tokengiamao.khonghople.hehe"}
    )
    assert response.status_code == 401   # Phải từ chối


def test_get_my_info():
    # Đăng ký
    reg_response = client.post("/register", json={
        "username": "myinfo",
        "email": "myinfo@test.com",
        "password": "pass123",
        "full_name": "Tên Của Tôi"
    })
    token = reg_response.json()["token"]

    # Lấy thông tin
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["username"] == "myinfo"
    assert response.json()["full_name"] == "Tên Của Tôi"
