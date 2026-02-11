from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import json
from pathlib import Path

security = HTTPBasic()

# Ruta del archivo users.json
BASE_DIR = Path(__file__).resolve().parent
USERS_FILE = BASE_DIR / "users.json"

def load_users():
    if not USERS_FILE.exists():
        raise RuntimeError("users.json no encontrado")
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    USERS = load_users()

    correct_password = USERS.get(credentials.username)

    if not correct_password or not secrets.compare_digest(
        credentials.password, correct_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
