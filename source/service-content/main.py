from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx   
import math
import time
import uuid

AUTH_SERVICE_URL = "http://auth-service:8001"

pois_db = {}

app = FastAPI(
    title="Zoo Content Service",
    description="Service quản lý địa điểm tham quan - Thảo Cầm Viên Sài Gòn",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_sample_data():
    sample_pois = [
        {
            "id": "tcv-001",
            "name": "Cổng Chính Thảo Cầm Viên",
            "description_vi": "Cổng chính Thảo Cầm Viên tọa lạc tại số 2 Nguyễn Bỉnh Khiêm, Quận 1. Được thành lập năm 1864 bởi nhà thực vật học người Pháp Jean Baptiste Louis Pierre, đây là một trong những vườn thú lâu đời nhất thế giới còn tồn tại đến nay.",
            "description_en": "The main gate of Saigon Zoo located at 2 Nguyen Binh Khiem Street, District 1. Founded in 1864 by French botanist Jean Baptiste Louis Pierre, it is one of the oldest zoos in the world still in operation.",
            "address": "2 Nguyễn Bỉnh Khiêm, Bến Nghé, Quận 1, TP.HCM",
            "latitude": 10.7876,
            "longitude": 106.7053,
            "trigger_radius_m": 35,
            "category": "landmark",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Saigon_Zoo.jpg/640px-Saigon_Zoo.jpg",
            "created_at": time.time()
        },
        {
            "id": "tcv-002",
            "name": "Khu Voi Châu Á",
            "description_vi": "Khu vực nuôi dưỡng đàn voi Châu Á trong môi trường bán tự nhiên rộng lớn. Du khách có thể quan sát voi tắm mát, ăn cỏ và tham gia chương trình tương tác giáo dục bảo tồn. Đây là một trong những điểm thu hút đông khách nhất của Thảo Cầm Viên.",
            "description_en": "The Asian Elephant enclosure provides a semi-natural habitat for a herd of Asian elephants. Visitors can watch elephants bathe, feed, and participate in educational conservation programs.",
            "address": "Khu A, Thảo Cầm Viên Sài Gòn, Quận 1, TP.HCM",
            "latitude": 10.7882,
            "longitude": 106.7058,
            "trigger_radius_m": 30,
            "category": "animal_zone",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Elephant_at_zoo.jpg/640px-Elephant_at_zoo.jpg",
            "created_at": time.time()
        },
        {
            "id": "tcv-003",
            "name": "Khu Hổ Trắng Bengal",
            "description_vi": "Khu bảo tồn Hổ Trắng Bengal - một trong những loài thú quý hiếm nhất thế giới. Không gian được thiết kế với suối nước, đá tảng và tán cây mô phỏng sinh thái rừng nhiệt đới tự nhiên. Mỗi ngày có 2 buổi cho hổ ăn vào lúc 9h và 15h.",
            "description_en": "The White Bengal Tiger Conservation Zone - home to one of the world's rarest animals. The enclosure features streams, rocks, and trees mimicking a natural tropical forest. Feeding sessions at 9AM and 3PM daily.",
            "address": "Khu B, Thảo Cầm Viên Sài Gòn, Quận 1, TP.HCM",
            "latitude": 10.7888,
            "longitude": 106.7065,
            "trigger_radius_m": 30,
            "category": "animal_zone",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/82_-_White_Tiger_%28Panthera_tigris_tigris%29.jpg/640px-82_-_White_Tiger_%28Panthera_tigris_tigris%29.jpg",
            "created_at": time.time()
        },
        {
            "id": "tcv-004",
            "name": "Bảo Tàng Lịch Sử TP.HCM",
            "description_vi": "Nằm ngay trong khuôn viên Thảo Cầm Viên, Bảo tàng Lịch sử lưu giữ hơn 40.000 cổ vật quý giá trải dài từ thời tiền sử đến đầu thế kỷ 20. Kiến trúc mang phong cách Đông Dương kết hợp nét văn hóa truyền thống Việt Nam.",
            "description_en": "Located within the Botanical Garden grounds, the Ho Chi Minh City History Museum houses over 40,000 precious artifacts spanning from prehistoric times to the early 20th century.",
            "address": "2 Nguyễn Bỉnh Khiêm, Bến Nghé, Quận 1, TP.HCM",
            "latitude": 10.7878,
            "longitude": 106.7048,
            "trigger_radius_m": 40,
            "category": "museum",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Vietnam_History_Museum_HCM.jpg/640px-Vietnam_History_Museum_HCM.jpg",
            "created_at": time.time()
        },
        {
            "id": "tcv-005",
            "name": "Vườn Thực Vật & Cây Cổ Thụ",
            "description_vi": "Vườn thực vật quy tụ hơn 1.800 cây cổ thụ hàng trăm năm tuổi và hàng nghìn loài thực vật nhiệt đới quý hiếm. Đây được ví như 'lá phổi xanh' giữa trung tâm thành phố, mang đến không gian mát mẻ, trong lành cho du khách.",
            "description_en": "The botanical garden hosts over 1,800 centuries-old trees and thousands of rare tropical plant species. Known as the 'green lung' of the city, it provides cool and refreshing space for visitors.",
            "address": "Khu Vườn Cây, Thảo Cầm Viên, Quận 1, TP.HCM",
            "latitude": 10.7891,
            "longitude": 106.7050,
            "trigger_radius_m": 35,
            "category": "botanical",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Botanical_garden_Saigon.jpg/640px-Botanical_garden_Saigon.jpg",
            "created_at": time.time()
        },
    ]
    for poi in sample_pois:
        pois_db[poi["id"]] = poi

seed_sample_data()

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

async def verify_user_token(authorization: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu token xác thực")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/verify",
                headers={"Authorization": authorization},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Token không hợp lệ")
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Auth Service không phản hồi. Vui lòng thử lại sau."
            )

class POICreate(BaseModel):
    name: str
    description_vi: str
    description_en: str
    address: str
    latitude: float
    longitude: float
    trigger_radius_m: float = 30.0
    category: str = "general"
    image_url: str = ""

@app.get("/")
def root():
    return {"service": "Content Service", "status": "đang chạy ✅", "total_pois": len(pois_db)}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "content"}


@app.get("/pois")
def get_all_pois():
    return {
        "total": len(pois_db),
        "pois": list(pois_db.values())
    }


@app.get("/pois/{poi_id}")
def get_poi_detail(poi_id: str):
    poi = pois_db.get(poi_id)
    if not poi:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy địa điểm với ID '{poi_id}'"
        )
    return poi


@app.get("/pois/nearby/search")
def find_nearby_pois(lat: float, lon: float, radius_m: float = 100):
    nearby = []
    for poi in pois_db.values():
        distance = haversine_distance(lat, lon, poi["latitude"], poi["longitude"])
        if distance <= radius_m:
            poi_with_distance = {**poi, "distance_m": round(distance, 1)}
            nearby.append(poi_with_distance)

    nearby.sort(key=lambda x: x["distance_m"])

    return {
        "your_location": {"lat": lat, "lon": lon},
        "search_radius_m": radius_m,
        "found": len(nearby),
        "pois": nearby
    }


@app.post("/pois")
async def create_poi(poi_data: POICreate, authorization: str = Header(None)):
    user_info = await verify_user_token(authorization)

    poi_id = f"tcv-{str(uuid.uuid4())[:8]}"
    new_poi = {
        "id": poi_id,
        **poi_data.dict(),
        "created_by": user_info.get("username"),
        "created_at": time.time()
    }
    pois_db[poi_id] = new_poi

    return {
        "message": "Đã thêm địa điểm thành công!",
        "poi": new_poi
    }


@app.delete("/pois/{poi_id}")
async def delete_poi(poi_id: str, authorization: str = Header(None)):
    await verify_user_token(authorization)

    if poi_id not in pois_db:
        raise HTTPException(status_code=404, detail="Không tìm thấy địa điểm")

    del pois_db[poi_id]
    return {"message": f"Đã xóa địa điểm '{poi_id}' thành công"}
