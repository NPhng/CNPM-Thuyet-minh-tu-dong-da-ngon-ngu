"""Tạo thêm tài khoản counter mẫu (idempotent). Dùng khi Mongo đã chạy."""

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

import main as auth_main


async def main():
    client = AsyncIOMotorClient(os.getenv("MONGO_URI", "mongodb://localhost:27018"))
    db = client[os.getenv("DB_NAME", "zoo_auth")]
    await db["users"].create_index("username", unique=True)
    await auth_main.seed_users(db)
    print("Seed users xong (admin + counter01 nếu chưa có).")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
