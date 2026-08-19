import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DATABASE = os.getenv("PG_DATABASE", "csu_control_room")

FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))

GENERATED_DIR = BASE_DIR / os.getenv("GENERATED_DIR", "./generated")
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

RENDER_DIR = BASE_DIR / "render"
ASSETS_DIR = RENDER_DIR / "assets"
