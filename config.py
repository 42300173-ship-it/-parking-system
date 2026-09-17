import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))

# Camera configuration
# 0 = Default webcam / laptop camera. Thay đổi thành 1, 2 nếu cắm webcam ngoài.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))

# Parking rates & timing
RATE_PER_MINUTE = int(os.getenv("RATE_PER_MINUTE", 1000))  # 1000 VND / phút
RFID_DEBOUNCE_SEC = float(os.getenv("RFID_DEBOUNCE_SEC", 3.0))

# Authentication
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "change-me")
APP_RESET_PIN = os.getenv("APP_RESET_PIN", "change-me")
SECRET_KEY = os.getenv("SECRET_KEY", "smart_parking_secret_key_2026")

# Database Configuration
# DB_TYPE có thể là "sqlite" hoặc "mysql"
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

# Cấu hình SQLite
SQLITE_PATH = os.path.join(BASE_DIR, "parking_logs.db")

# Cấu hình MySQL (khi cài XAMPP/MySQL)
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "parking_system")

# Thư mục lưu ảnh chụp biển số tự động
CAPTURES_DIR = os.path.join(BASE_DIR, "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)
