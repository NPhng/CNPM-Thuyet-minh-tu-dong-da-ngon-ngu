from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import edge_tts   
import httpx
import asyncio
import os
import hashlib     
import time

CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://content-service:8002")
LOCALIZATION_SERVICE_URL = os.getenv("LOCALIZATION_SERVICE_URL", "http://localization-service:8004")
AUDIO_DIR = os.getenv("AUDIO_DIR", "/app/audio_files")  # Thư mục lưu file MP3

# Mapping ngôn ngữ  giọng đọc
VOICE_MAP = {
    "vi": "vi-VN-HoaiMyNeural",       # Tiếng Việt - Giọng Hoài My
    "en": "en-US-JennyNeural",         # Tiếng Anh - Giọng Jenny
    "zh": "zh-CN-XiaoxiaoNeural",      # Tiếng Trung - Giọng Xiaoxiao
    "ja": "ja-JP-NanamiNeural",        # Tiếng Nhật - Giọng Nanami
    "ko": "ko-KR-SunHiNeural",         # Tiếng Hàn - Giọng Sun Hi
}

# Đảm bảo thư mục audio tồn tại
os.makedirs(AUDIO_DIR, exist_ok=True)

app = FastAPI(
    title="Zoo Audio Service",
    description="Service tạo âm thanh TTS đa ngôn ngữ - Thảo Cầm Viên Sài Gòn",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def make_audio_filename(text: str, language: str) -> str:
    content_hash = hashlib.md5(f"{text}_{language}".encode()).hexdigest()
    return f"{content_hash}.mp3"


async def generate_tts_audio(text: str, language: str, output_path: str):
    voice = VOICE_MAP.get(language, VOICE_MAP["vi"])  # Mặc định tiếng Việt nếu không tìm thấy
    
    # Tạo đối tượng Communicate của edge-tts
    communicate = edge_tts.Communicate(text=text, voice=voice)
    
    # Lưu file audio
    await communicate.save(output_path)


async def get_poi_from_content_service(poi_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{CONTENT_SERVICE_URL}/pois/{poi_id}",
                timeout=5.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy địa điểm '{poi_id}'")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Content Service lỗi")
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Content Service không phản hồi"
            )


async def get_poi_from_localization_service(poi_id: str, language: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LOCALIZATION_SERVICE_URL}/poi/{poi_id}?lang={language}",
                timeout=10.0
            )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy địa điểm '{poi_id}'")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="Localization Service lỗi")
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail="Localization Service không phản hồi"
            )



class TextToSpeechRequest(BaseModel):
    """Tạo audio từ text tùy ý"""
    text: str
    language: str = "vi"  


class AudioStatus(BaseModel):
    """Trạng thái của file audio"""
    poi_id: str
    language: str
    status: str
    file_path: str
    file_size_kb: float

# API endpoints


@app.get("/")
def root():
    return {
        "service": "Audio Service",
        "status": "đang chạy ",
        "supported_languages": list(VOICE_MAP.keys()),
        "voices": VOICE_MAP
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "audio"}


@app.post("/tts")
async def text_to_speech(request: TextToSpeechRequest):
    if request.language not in VOICE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Ngôn ngữ '{request.language}' không được hỗ trợ. Chọn: {list(VOICE_MAP.keys())}"
        )

    if len(request.text) > 5000:
        raise HTTPException(status_code=400, detail="Text quá dài (tối đa 5000 ký tự)")

    # Tạo tên file từ nội dung (cache - nếu đã tạo rồi thì không tạo lại)
    filename = make_audio_filename(request.text, request.language)
    output_path = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(output_path):
        # Chưa có → tạo mới
        await generate_tts_audio(request.text, request.language, output_path)

    file_size = os.path.getsize(output_path) / 1024  # Chuyển sang KB

    return {
        "message": "Tạo audio thành công!",
        "language": request.language,
        "voice_used": VOICE_MAP[request.language],
        "audio_url": f"/audio/download/{filename}",
        "file_size_kb": round(file_size, 1)
    }


@app.get("/tts/poi/{poi_id}")
async def generate_poi_audio(poi_id: str, language: str = "vi"):
    if language not in VOICE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Ngôn ngữ '{language}' không được hỗ trợ. Chọn: {list(VOICE_MAP.keys())}"
        )

    poi_name = ""
    text = ""
    actual_lang = language

    # Bước 1: Gọi Localization Service để lấy bản dịch chuẩn
    try:
        localized = await get_poi_from_localization_service(poi_id, language)
        poi_name = localized.get("poi_name", "")
        text = localized.get("text", "")
        actual_lang = localized.get("actual_lang", language)
    except HTTPException:
        # Nếu Localization Service lỗi hoặc không khả dụng, fallback sang Content Service
        poi = await get_poi_from_content_service(poi_id)
        poi_name = poi.get("name", "")
        if language == "vi":
            text = poi.get("description_vi", poi.get("description_en", ""))
            actual_lang = "vi"
        else:
            text = poi.get("description_en", poi.get("description_vi", ""))
            actual_lang = "en"

    if not text:
        raise HTTPException(status_code=404, detail="Không có nội dung thuyết minh cho địa điểm này")

    # Thêm tên địa điểm vào đầu (nếu có tên)
    full_text = f"{poi_name}. {text}" if poi_name else text

    # Bước 2: Tạo file MP3 theo đúng ngôn ngữ thực tế
    filename = make_audio_filename(f"{poi_id}_{full_text}", actual_lang)
    output_path = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(output_path):
        await generate_tts_audio(full_text, actual_lang, output_path)

    file_size = os.path.getsize(output_path) / 1024

    return {
        "poi_id": poi_id,
        "poi_name": poi_name,
        "language": actual_lang,
        "voice_used": VOICE_MAP.get(actual_lang, VOICE_MAP["vi"]),
        "audio_url": f"/audio/download/{filename}",
        "file_size_kb": round(file_size, 1),
        "text_preview": full_text[:100] + "..." if len(full_text) > 100 else full_text
    }


@app.get("/audio/download/{filename}")
async def download_audio(filename: str):
    # Chỉ cho phép file .mp3 để tránh lỗ hổng bảo mật path traversal
    if not filename.endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file MP3")

    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File audio không tồn tại")

    return FileResponse(
        path=file_path,
        media_type="audio/mpeg",
        filename=filename
    )


@app.get("/audio/list")
def list_audio_files():
    """Xem danh sách tất cả file audio đã tạo"""
    files = []
    if os.path.exists(AUDIO_DIR):
        for filename in os.listdir(AUDIO_DIR):
            if filename.endswith(".mp3"):
                file_path = os.path.join(AUDIO_DIR, filename)
                files.append({
                    "filename": filename,
                    "size_kb": round(os.path.getsize(file_path) / 1024, 1),
                    "download_url": f"/audio/download/{filename}"
                })
    return {
        "total_files": len(files),
        "files": files
    }
