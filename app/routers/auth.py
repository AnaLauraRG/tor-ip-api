"""Inicio de sesión."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import TokenResponse
from app.security import authenticate, create_access_token, login_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Obtener un token JWT")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Recibe usuario y contraseña (formulario) y devuelve un token Bearer.

    Tras demasiados intentos fallidos desde una misma IP, responde 429.
    """
    # Se registra el usuario intentado para la auditoría (nunca la contraseña).
    request.state.username = form.username[:50]
    client_key = request.client.host if request.client else "desconocido"

    retry_after = login_limiter.retry_after(client_key)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intenta más tarde.",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate(db, form.username, form.password)
    if user is None:
        login_limiter.register_failure(client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_limiter.reset(client_key)
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=settings.jwt_expire_min * 60,
    )
