import pytest
from fastapi.testclient import TestClient  
from main import app, fake_users_db        

# Tạo client để gọi API trong test
client = TestClient(app)

# Hàm chạy trước sau mỗi test 

@pytest.fixture(autouse=True)
def clear_database():
   
    fake_users_db.clear()  # Xóa hết user cũ
    yield                   # Cho test chạy
    fake_users_db.clear()  # Xóa lại sau test


#Kiểm tra service có chạy không
def test_service_root():
    """Test: Endpoint / trả về thông tin service"""
    response = client.get("/")
    assert response.status_code == 200           
    data = response.json()
    assert data["service"] == "Auth Service"     
    assert data["status"] == "đang chạy "


def test_health_check():
    """Test: Endpoint /health trả về ok"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

#Đăng ký tài khoản

def test_register_success():
    """Test: Đăng ký thành công với thông tin hợp lệ"""
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
    """Test: Đăng ký thất bại nếu username đã tồn tại"""
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

#Đăng nhập
def test_login_success():
    """Test: Đăng nhập thành công sau khi đã đăng ký"""
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
    """Test: Đăng nhập thất bại nếu sai mật khẩu"""
    client.post("/register", json={
        "username": "testuser2",
        "email": "test2@test.com",
        "password": "matkhaudung"
    })

    response = client.post("/login", json={
        "username": "testuser2",
        "password": "matkhausai"  
    })
    assert response.status_code == 401   # HTTP 401 = không có quyền


def test_login_user_not_found():
    """Test: Đăng nhập thất bại nếu username không tồn tại"""
    response = client.post("/login", json={
        "username": "khongtontai",
        "password": "batkymatkhau"
    })
    assert response.status_code == 401

#Verify Token
def test_verify_valid_token():
    """Test: Token vừa đăng nhập phải hợp lệ"""
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
    """Test: Token giả mạo phải bị từ chối"""
    response = client.get(
        "/verify",
        headers={"Authorization": "Bearer tokengiamao.khonghople.hehe"}
    )
    assert response.status_code == 401   # Phải từ chối


def test_get_my_info():
    """Test: Lấy thông tin cá nhân sau khi đăng nhập"""
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
