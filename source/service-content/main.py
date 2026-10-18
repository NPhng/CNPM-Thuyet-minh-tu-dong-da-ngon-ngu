from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import uuid
import time

AUTH_SERVICE_URL = "http://auth-service:8001"  
poi_db = {
    "tcv-001": {
        "id": "tcv-001",
        "name": "Cổng Chính",
        "name_en": "Main Gate",
        "description_vi": (
            "Cổng chính Thảo Cầm Viên Sài Gòn được xây dựng từ năm 1864, "
            "là biểu tượng lịch sử hơn 160 năm của vườn thú lâu đời nhất Việt Nam. "
            "Cổng mang kiến trúc Pháp cổ điển, là điểm chụp ảnh yêu thích của du khách."
        ),
        "description_en": (
            "The main gate of Saigon Zoo and Botanical Gardens, built in 1864, "
            "is a historic symbol of Vietnam's oldest zoo with over 160 years of history. "
            "It features classic French architecture and is a popular photography spot."
        ),
        "latitude": 10.7876,
        "longitude": 106.7053,
        "radius_m": 35,
        "created_at": time.time()
    },
    "tcv-002": {
        "id": "tcv-002",
        "name": "Khu Voi Châu Á",
        "name_en": "Asian Elephant Zone",
        "description_vi": (
            "Khu nuôi voi Châu Á là một trong những điểm hấp dẫn nhất của Thảo Cầm Viên. "
            "Hiện vườn đang chăm sóc 3 cá thể voi Châu Á, trong đó có 1 voi con sinh năm 2019. "
            "Voi Châu Á nhỏ hơn voi Châu Phi và có tai nhỏ hơn, đặc trưng bởi chiếc vòi linh hoạt."
        ),
        "description_en": (
            "The Asian Elephant zone is one of the most attractive areas of the zoo. "
            "The zoo currently cares for 3 Asian elephants, including one calf born in 2019. "
            "Asian elephants are smaller than African elephants with distinctive smaller ears."
        ),
        "latitude": 10.7882,
        "longitude": 106.7058,
        "radius_m": 30,
        "created_at": time.time()
    },
    "tcv-003": {
        "id": "tcv-003",
        "name": "Khu Hổ Trắng Bengal",
        "name_en": "Bengal White Tiger Zone",
        "description_vi": (
            "Hổ trắng Bengal là loài cực kỳ quý hiếm, kết quả của đột biến gen tự nhiên. "
            "Thảo Cầm Viên là một trong số ít vườn thú tại Việt Nam nuôi dưỡng thành công loài này. "
            "Hổ trắng có bộ lông trắng với sọc đen, mắt xanh dương đặc trưng."
        ),
        "description_en": (
            "The Bengal White Tiger is an extremely rare species resulting from a natural genetic mutation. "
            "Saigon Zoo is one of the few zoos in Vietnam to successfully house this species. "
            "White tigers have white fur with black stripes and characteristic blue eyes."
        ),
        "latitude": 10.7888,
        "longitude": 106.7065,
        "radius_m": 30,
        "created_at": time.time()
    },
    "tcv-004": {
        "id": "tcv-004",
        "name": "Bảo Tàng Lịch Sử",
        "name_en": "History Museum",
        "description_vi": (
            "Bảo Tàng Lịch Sử Việt Nam tại TP.HCM nằm ngay trong khuôn viên Thảo Cầm Viên. "
            "Nơi đây lưu giữ hơn 40.000 hiện vật lịch sử từ thời tiền sử đến thế kỷ 20, "
            "bao gồm các cổ vật Óc Eo, đồ gốm Chăm Pa và nhiều bảo vật quốc gia."
        ),
        "description_en": (
            "The Vietnam History Museum in Ho Chi Minh City is located within the zoo grounds. "
            "It houses over 40,000 historical artifacts from prehistoric times to the 20th century, "
            "including Óc Eo relics, Cham pottery, and many national treasures."
        ),
        "latitude": 10.7878,
        "longitude": 106.7048,
        "radius_m": 40,
        "created_at": time.time()
    },
    "tcv-005": {
        "id": "tcv-005",
        "name": "Vườn Thực Vật Cổ Thụ",
        "name_en": "Ancient Botanical Garden",
        "description_vi": (
            "Vườn thực vật với hàng trăm cây cổ thụ hàng trăm năm tuổi là lá phổi xanh của thành phố. "
            "Nơi đây có hơn 1.800 loài thực vật nhiệt đới, trong đó có nhiều loài quý hiếm. "
            "Bóng mát của những tán cây cổ thụ tạo nên không gian yên bình giữa lòng đô thị."
        ),
        "description_en": (
            "The botanical garden with hundreds of ancient trees is the green lung of the city. "
            "It houses over 1,800 tropical plant species, including many rare varieties. "
            "The shade of ancient tree canopies creates a peaceful space in the heart of the city."
        ),
        "latitude": 10.7891,
        "longitude": 106.7050,
        "radius_m": 35,
        "created_at": time.time()
    }
}

app = FastAPI(
    title="Zoo Content Service",
    description="Service quản lý nội dung địa điểm (POI) - Thảo Cầm Viên Sài Gòn",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class POICreate(BaseModel):
    """Dữ liệu để tạo địa điểm mới"""
    name: str
    name_en: str
    description_vi: str
    description_en: str
    latitude: float
    longitude: float
    radius_m: float = 30.0

async def verify_token_from_auth(authorization: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/verify",
                headers={"Authorization": authorization},
                timeout=5.0
            )
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Auth Service lỗi")
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Auth Service không phản hồi - vui lòng thử lại sau"
            )


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371000  # Bán kính Trái Đất (mét)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@app.get("/")
def root():
    return {
        "service": "Content Service",
        "status": "đang chạy ",
        "total_pois": len(poi_db),
        "version": "1.0.0"
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "content"}


@app.get("/pois")
def get_all_pois():
    pois = list(poi_db.values())
    return {
        "total": len(pois),
        "pois": pois
    }


@app.get("/pois/{poi_id}")
def get_poi(poi_id: str):
    poi = poi_db.get(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy địa điểm với ID '{poi_id}'"
        )
    return poi


@app.get("/pois/nearby/search")
def search_nearby_pois(lat: float, lon: float, radius_m: float = 50.0):
    nearby = []
    for poi in poi_db.values():
        distance = calculate_distance(lat, lon, poi["latitude"], poi["longitude"])
        if distance <= radius_m:
            nearby.append({
                **poi,
                "distance_m": round(distance, 1)  
            })

    nearby.sort(key=lambda x: x["distance_m"])

    return {
        "search_location": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "found": len(nearby),
        "pois": nearby
    }


@app.post("/pois", status_code=201)
async def create_poi(
    poi_data: POICreate,
    authorization: Optional[str] = Header(None)
):
 
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để thêm địa điểm. Gửi kèm Authorization: Bearer <token>"
        )

    user_info = await verify_token_from_auth(authorization)

    new_id = f"tcv-{str(uuid.uuid4())[:6]}"

    new_poi = {
        "id": new_id,
        "name": poi_data.name,
        "name_en": poi_data.name_en,
        "description_vi": poi_data.description_vi,
        "description_en": poi_data.description_en,
        "latitude": poi_data.latitude,
        "longitude": poi_data.longitude,
        "radius_m": poi_data.radius_m,
        "created_by": user_info.get("username", "unknown"),
        "created_at": time.time()
    }

    poi_db[new_id] = new_poi

    return {
        "message": "Thêm địa điểm thành công!",
        "poi": new_poi
    }


@app.delete("/pois/{poi_id}")
async def delete_poi(
    poi_id: str,
    authorization: Optional[str] = Header(None)
):
    
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để xóa địa điểm"
        )

    await verify_token_from_auth(authorization)

    if poi_id not in poi_db:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy địa điểm '{poi_id}'"
        )

    deleted_poi = poi_db.pop(poi_id)

    return {
        "message": f"Đã xóa địa điểm '{deleted_poi['name']}' thành công",
        "deleted_poi_id": poi_id
    }
