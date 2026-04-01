"""
Utilidades de autenticación:
  - Hash de contraseñas con bcrypt
  - Creación y decodificación de JWT
  - Cifrado/descifrado Fernet para tokens sensibles en BD
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import jwt
from passlib.context import CryptContext

# ─── Configuración desde .env ─────────────────────────────────────────────────
SECRET_KEY      = os.getenv("JWT_SECRET_KEY",      "CHANGE_ME_IN_PRODUCTION_NOW")
ALGORITHM       = os.getenv("JWT_ALGORITHM",       "HS256")
EXPIRE_MINUTES  = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))   # 8 horas
FERNET_KEY      = os.getenv("FERNET_KEY", "")

# ─── Password hashing ─────────────────────────────────────────────────────────
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, tenant_id: int, role: str) -> str:
    payload = {
        "user_id":   user_id,
        "tenant_id": tenant_id,
        "role":      role,
        "exp":       datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica y valida el JWT. Lanza JWTError si es inválido/expirado."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ─── Fernet (cifrado simétrico para secrets en BD) ────────────────────────────

def _fernet() -> Optional[Fernet]:
    if not FERNET_KEY:
        return None
    key = FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Cifra un string. Si FERNET_KEY no está configurada devuelve el valor sin cifrar."""
    if not value:
        return value
    f = _fernet()
    if not f:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Descifra un string. Si falla (sin clave o valor sin cifrar) devuelve el valor original."""
    if not value:
        return value
    f = _fernet()
    if not f:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return value   # fallback: devolver tal cual (puede ser valor sin cifrar)
