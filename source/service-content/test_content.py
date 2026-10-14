import pytest
import math
from fastapi.testclient import TestClient
from main import app, pois_db, haversine_distance

client = TestClient(app)


# Test 1: Service cơ bản
def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Content Service"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# Test 2: Lấy danh sách POI
def test_get_all_pois():
    response = client.get("/pois")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5    # Có 5 địa điểm seed sẵn
    assert len(data["pois"]) == 5


def test_get_poi_detail_success():
    response = client.get("/pois/tcv-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tcv-001"
    assert "Cổng Chính" in data["name"]
    assert "latitude" in data
    assert "longitude" in data


def test_get_poi_detail_not_found():
    response = client.get("/pois/khong-ton-tai-123")
    assert response.status_code == 404


# Test 3: Công thức Haversine
def test_haversine_same_location():
    distance = haversine_distance(10.7876, 106.7053, 10.7876, 106.7053)
    assert distance == 0.0


def test_haversine_known_distance():
    distance = haversine_distance(10.7876, 106.7053, 10.7882, 106.7058)
    assert 60 < distance < 110, f"Khoảng cách phải khoảng 84m, nhưng got {distance:.1f}m"


def test_haversine_larger_distance():
    distance = haversine_distance(21.0285, 105.8542, 10.7769, 106.7009)
    assert distance > 1_000_000

# Test 4: Tìm kiếm nearby
def test_nearby_search_finds_poi():
    # Đứng đúng tại vị trí cổng chính
    response = client.get("/pois/nearby/search?lat=10.7876&lon=106.7053&radius_m=10")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] >= 1   # Phải tìm thấy ít nhất 1 POI
    
    # POI đầu tiên phải là cổng chính
    poi_ids = [p["id"] for p in data["pois"]]
    assert "tcv-001" in poi_ids


def test_nearby_search_empty_when_far():
    # Tọa độ ở Hà Nội (rất xa Thảo Cầm Viên)
    response = client.get("/pois/nearby/search?lat=21.0285&lon=105.8542&radius_m=100")
    assert response.status_code == 200
    data = response.json()
    assert data["found"] == 0   # Không tìm thấy gì


def test_nearby_returns_sorted_by_distance():
    response = client.get("/pois/nearby/search?lat=10.7880&lon=106.7055&radius_m=200")
    assert response.status_code == 200
    pois = response.json()["pois"]
    
    if len(pois) >= 2:
        # Khoảng cách phải tăng dần
        distances = [p["distance_m"] for p in pois]
        assert distances == sorted(distances), "Phải sắp xếp theo khoảng cách tăng dần"
