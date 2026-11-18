"""Middleware de auditoría y cabeceras de seguridad.

Cada petición (salvo /health, que consulta el healthcheck cada 30 segundos)
queda registrada en la tabla audit_log y en el log de la aplicación.
"""

import logging
import time

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal
from app.models import AuditLog

logger = logging.getLogger("app.audit")

_SKIP_PATHS = {"/health"}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def _save(entry: AuditLog) -> None:
    with SessionLocal() as db:
        db.add(entry)
        db.commit()


async def audit_middleware(request: Request, call_next) -> Response:
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
    finally:
        if request.url.path not in _SKIP_PATHS:
            entry = AuditLog(
                # Lo fija la dependencia de autenticación o el endpoint de login.
                username=getattr(request.state, "username", None),
                method=request.method,
                path=request.url.path[:255],
                status_code=status_code,
                client_ip=request.client.host if request.client else None,
                user_agent=(request.headers.get("user-agent") or "")[:255] or None,
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
            logger.info(
                "user=%s method=%s path=%s status=%s ip=%s duration_ms=%s",
                entry.username or "-",
                entry.method,
                entry.path,
                entry.status_code,
                entry.client_ip,
                entry.duration_ms,
            )
            try:
                await run_in_threadpool(_save, entry)
            except Exception:
                # Un fallo al auditar no debe tumbar la petición, pero sí quedar en el log.
                logger.exception("No se pudo guardar el registro de auditoría")
