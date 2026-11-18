"""Contraseñas, tokens JWT, control de acceso por rol y límite de intentos de login."""

import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Role, User, utcnow

JWT_ALGORITHM = "HS256"
# bcrypt solo considera los primeros 72 bytes de la contraseña.
BCRYPT_MAX_BYTES = 72

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o token expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


# --- Contraseñas ---


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode()
    if len(data) > BCRYPT_MAX_BYTES:
        return False
    return bcrypt.checkpw(data, password_hash.encode())


@lru_cache(maxsize=1)
def _dummy_hash() -> bytes:
    return bcrypt.hashpw(
        secrets.token_bytes(16), bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    )


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        # Se verifica contra un hash de relleno con el mismo costo, para que el
        # login tarde lo mismo exista o no el usuario y no se pueda averiguar
        # qué usuarios existen midiendo el tiempo de respuesta.
        bcrypt.checkpw(password.encode()[:BCRYPT_MAX_BYTES], _dummy_hash())
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


# --- Tokens ---


def create_access_token(user: User) -> str:
    now = utcnow()
    payload = {
        "sub": user.username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_min),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise _CREDENTIALS_ERROR
    try:
        # Se fija el algoritmo esperado: así se rechazan tokens con "alg": "none"
        # o firmados con otro algoritmo.
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        raise _CREDENTIALS_ERROR from None

    # El rol y el estado se leen de la base, no del token: si un usuario se
    # desactiva, pierde el acceso aunque su token siga vigente.
    user = db.scalar(select(User).where(User.username == payload["sub"]))
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    request.state.username = user.username
    return user


def require_role(*roles: Role):
    allowed = {role.value for role in roles}

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para esta operación",
            )
        return user

    return dependency


require_reader = require_role(Role.READER, Role.ADMIN)
require_admin = require_role(Role.ADMIN)


# --- Límite de intentos de login ---


class LoginRateLimiter:
    """Cuenta los logins fallidos por IP en una ventana deslizante.

    Vive en memoria: sirve para una sola instancia de la API. Con varias
    instancias habría que moverlo a Redis o a un WAF.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        window = settings.login_window_min * 60
        attempts = self._failures[key]
        while attempts and now - attempts[0] > window:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int:
        """Segundos que faltan para poder reintentar, o 0 si no está bloqueado."""
        with self._lock:
            now = time.monotonic()
            attempts = self._prune(key, now)
            if len(attempts) < settings.login_max_attempts:
                return 0
            return max(1, int(settings.login_window_min * 60 - (now - attempts[0])))

    def register_failure(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


login_limiter = LoginRateLimiter()
