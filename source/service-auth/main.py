from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import jwt           
import bcrypt        
import time
import uuid          

SECRET_KEY = "zoo-narration-secret-2024"   
ALGORITHM = "HS256"                         
TOKEN_EXPIRE_MINUTES = 30                   

fake_users_db = {}

# Khởi tạo  FastAPI
app = FastAPI(
    title="Zoo Auth Service",
    description="Service xác thực người dùng - Hệ thống Thuyết minh Thảo Cầm Viên",
    version="1.0.0"
)

# Cho phép frontend gọi API tránh lỗi CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đối tượng kiểm tra Bearer token trong header
security = HTTPBearer()

class RegisterRequest(BaseModel):
    """Dữ liệu khi đăng ký"""
    username: str
    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    """Dữ liệu khi đăng nhập"""
    username: str
    password: str


class UserResponse(BaseModel):
    """Dữ liệu trả về sau đăng nhập thành công"""
    user_id: str
    username: str
    email: str
    full_name: str
    token: str        
    expires_in: int   


def hash_password(plain_password: str) -> str:
    
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def check_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def create_jwt_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,          
        "username": username,
        "iat": time.time(),          # Thời điểm tạo token
        "exp": time.time() + (TOKEN_EXPIRE_MINUTES * 60)  # Thời điểm hết hạn
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_jwt_token(token: str) -> dict:
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token đã hết hạn, vui lòng đăng nhập lại")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")


#API endpoint
@app.get("/")
def root():
    #Kiểm tra service có đang chạy không
    return {"service": "Auth Service", "status": "đang chạy ", "version": "1.0.0"}


@app.get("/health")
def health_check():
    #Health check - dùng cho Docker và CI/CD kiểm tra service còn sống không
    return {"status": "ok", "service": "auth"}


@app.post("/register", response_model=UserResponse)
def register(request: RegisterRequest):
    
    
    # Kiểm tra username đã có chưa
    if request.username in fake_users_db:
        raise HTTPException(
            status_code=400,
            detail=f"Username '{request.username}' đã được sử dụng"
        )

    # Tạo tài khoản mới
    user_id = str(uuid.uuid4())  
    new_user = {
        "id": user_id,
        "username": request.username,
        "email": request.email,
        "full_name": request.full_name,
        "password_hashed": hash_password(request.password),  
        "created_at": time.time()
    }

    # Lưu vào database bộ nhớ tạm
    fake_users_db[request.username] = new_user

    # Tạo token và trả về
    token = create_jwt_token(user_id, request.username)
    return UserResponse(
        user_id=user_id,
        username=request.username,
        email=request.email,
        full_name=request.full_name,
        token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60
    )


@app.post("/login", response_model=UserResponse)
def login(request: LoginRequest):
    # Tìm user trong database
    user = fake_users_db.get(request.username)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Username hoặc mật khẩu không đúng"
        )

    # Kiểm tra mật khẩu
    if not check_password(request.password, user["password_hashed"]):
        raise HTTPException(
            status_code=401,
            detail="Username hoặc mật khẩu không đúng"
        )

    # Đăng nhập thành công thì tạo token
    token = create_jwt_token(user["id"], user["username"])
    return UserResponse(
        user_id=user["id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        token=token,
        expires_in=TOKEN_EXPIRE_MINUTES * 60
    )


@app.get("/verify")
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
   
    token = credentials.credentials
    payload = decode_jwt_token(token)
    return {
        "valid": True,
        "user_id": payload.get("sub"),
        "username": payload.get("username")
    }


@app.get("/me")
def get_my_info(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Lấy thông tin của chính mình (cần token hợp lệ)"""
    token = credentials.credentials
    payload = decode_jwt_token(token)
    username = payload.get("username")

    user = fake_users_db.get(username)
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin người dùng")

    return {
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "full_name": user["full_name"]
    }
