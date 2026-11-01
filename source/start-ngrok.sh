#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

if ! docker info >/dev/null 2>&1; then
  echo "[LOI] Docker chua chay hoac user chua co quyen. Thu: sudo systemctl start docker ; sudo usermod -aG docker \$USER (roi dang xuat/dang nhap lai)"
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Da tao .env. Hay sua JWT_SECRET, INTERNAL_SERVICE_KEY, ADMIN_PASSWORD, COUNTER_PASSWORD (vd: nano .env) roi chay lai."
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "[LOI] Chua cai ngrok. Xem huong dan cai o ngrok.com/download"
  exit 1
fi

docker compose up --build -d || { echo "[LOI] docker compose that bai"; exit 1; }
echo "Doi cac service khoi dong..."
sleep 20
docker compose ps
echo
echo "Thu tren may: http://localhost:8080"
echo "Link gui moi nguoi nam o dong Forwarding (https://....ngrok-free.app). Dung: Ctrl+C"
ngrok http 8080
