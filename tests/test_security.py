"""Autenticación, roles, auditoría, usuarios y actualización manual de fuentes."""

from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.models import AuditLog, SourceStatus, User, utcnow
from tests.conftest import ADMIN, READER, auth_headers, login

PROTECTED = [
    ("get", "/ips"),
    ("get", "/ips/filtered"),
    ("get", "/exclusions"),
    ("post", "/exclusions"),
    ("delete", "/exclusions/1.1.1.1"),
    ("post", "/sources/refresh"),
    ("get", "/users"),
    ("post", "/users"),
    ("get", "/audit"),
]

ADMIN_ONLY = [
    ("post", "/exclusions", {"ip": "1.1.1.1"}),
    ("delete", "/exclusions/1.1.1.1", None),
    ("post", "/sources/refresh", None),
    ("get", "/users", None),
    ("post", "/users", {"username": "nuevo", "password": "una-clave-larga-1"}),
    ("get", "/audit", None),
]


# --- Login ---


def test_login_returns_token(client):
    response = login(client, *ADMIN)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_expire_min * 60
    claims = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == "admin"
    # El token no lleva el rol ni datos sensibles: el rol se consulta en la base.
    assert set(claims) == {"sub", "iat", "exp"}


@pytest.mark.parametrize(
    "credentials",
    [("admin", "incorrecta"), ("no-existe", "admin-password-123"), ("admin", "")],
)
def test_login_rejects_bad_credentials(client, credentials):
    response = login(client, *credentials)
    assert response.status_code in (401, 422)


def test_login_same_error_for_unknown_user_and_bad_password(client):
    unknown = login(client, "no-existe", "x")
    wrong = login(client, "admin", "x")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_login_rate_limited(client):
    for _ in range(settings.login_max_attempts):
        assert login(client, "admin", "incorrecta").status_code == 401
    blocked = login(client, *ADMIN)
    # Bloqueado incluso con la contraseña correcta.
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_successful_login_resets_failures(client):
    for _ in range(settings.login_max_attempts - 1):
        login(client, "admin", "incorrecta")
    assert login(client, *ADMIN).status_code == 200
    for _ in range(settings.login_max_attempts - 1):
        assert login(client, "admin", "incorrecta").status_code == 401


def test_inactive_user_cannot_login_and_loses_access(client, db):
    headers = auth_headers(client, READER)
    user = db.scalar(select(User).where(User.username == READER[0]))
    user.is_active = False
    db.commit()
    assert client.get("/ips", headers=headers).status_code == 401
    assert login(client, *READER).status_code == 401


# --- Tokens ---


@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_endpoints_require_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def _token(**overrides):
    now = utcnow()
    payload = {"sub": "admin", "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(overrides)
    secret = payload.pop("secret", settings.jwt_secret)
    algorithm = payload.pop("algorithm", "HS256")
    return jwt.encode({k: v for k, v in payload.items() if v is not None}, secret, algorithm)


@pytest.mark.parametrize(
    "token",
    [
        "no-es-un-token",
        _token(exp=utcnow() - timedelta(minutes=1)),
        _token(secret="otro-secreto-de-al-menos-32-caracteres!"),
        _token(sub="usuario-inexistente"),
        _token(exp=None),
        _token(sub=None),
        _token(algorithm="HS512"),
    ],
    ids=["basura", "expirado", "firma-ajena", "usuario-inexistente", "sin-exp", "sin-sub", "otro-alg"],
)
def test_invalid_tokens_rejected(client, token):
    response = client.get("/ips", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_unsigned_token_rejected(client):
    # Ataque clásico: token con "alg": "none" y sin firma.
    payload = {"sub": "admin", "exp": utcnow() + timedelta(minutes=5)}
    token = jwt.encode(payload, key=None, algorithm="none")
    response = client.get("/ips", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# --- Roles ---


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
def test_reader_cannot_use_admin_endpoints(client, reader, method, path, body):
    response = client.request(method, path, json=body, headers=reader)
    assert response.status_code == 403


def test_role_change_applies_to_existing_token(client, db):
    headers = auth_headers(client, READER)
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=headers).status_code == 403
    user = db.scalar(select(User).where(User.username == READER[0]))
    user.role = "admin"
    db.commit()
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=headers).status_code == 201


# --- Usuarios ---


def test_admin_creates_reader(client, admin):
    response = client.post(
        "/users", json={"username": "analista", "password": "una-clave-larga-1"}, headers=admin
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "reader"
    assert "password" not in body and "password_hash" not in body

    new_headers = auth_headers(client, ("analista", "una-clave-larga-1"))
    assert client.get("/ips", headers=new_headers).status_code == 200
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=new_headers).status_code == 403


def test_create_user_validation(client, admin):
    cases = [
        {"username": "ab", "password": "una-clave-larga-1"},
        {"username": "con espacio", "password": "una-clave-larga-1"},
        {"username": "valido", "password": "corta"},
        {"username": "valido", "password": "x" * 73},
        {"username": "valido", "password": "una-clave-larga-1", "role": "superadmin"},
    ]
    for body in cases:
        assert client.post("/users", json=body, headers=admin).status_code == 422


def test_create_duplicate_user(client, admin):
    body = {"username": "lector", "password": "una-clave-larga-1"}
    assert client.post("/users", json=body, headers=admin).status_code == 409


def test_passwords_are_hashed(client, db):
    user = db.scalar(select(User).where(User.username == "admin"))
    assert user.password_hash.startswith("$2b$")
    assert ADMIN[1] not in user.password_hash


# --- Auditoría ---


def test_audit_records_requests(client, admin, reader, db):
    client.get("/ips", headers=reader)
    client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=reader)
    client.get("/ips")
    login(client, "admin", "clave-incorrecta")

    entries = client.get("/audit", headers=admin).json()
    by_request = {(e["method"], e["path"], e["status_code"]): e for e in entries}

    assert by_request[("GET", "/ips", 200)]["username"] == "lector"
    assert by_request[("POST", "/exclusions", 403)]["username"] == "lector"
    assert by_request[("GET", "/ips", 401)]["username"] is None
    failed_login = by_request[("POST", "/auth/login", 401)]
    assert failed_login["username"] == "admin"
    assert failed_login["client_ip"]
    assert all(e["path"] != "/health" for e in entries)


def test_audit_never_stores_passwords(client, db):
    login(client, "admin", "clave-super-secreta-9")
    for entry in db.scalars(select(AuditLog)).all():
        for value in vars(entry).values():
            assert "clave-super-secreta-9" not in str(value)


def test_audit_filter_and_pagination(client, admin, reader):
    for _ in range(3):
        client.get("/ips", headers=reader)
    only_reader = client.get("/audit", params={"username": "lector"}, headers=admin).json()
    assert only_reader and all(e["username"] == "lector" for e in only_reader)
    assert len(client.get("/audit", params={"limit": 2}, headers=admin).json()) == 2
    assert client.get("/audit", params={"limit": 501}, headers=admin).status_code == 422


# --- Actualización manual ---


def test_refresh_respects_danme_minimum(client, admin, db, monkeypatch):
    calls = []

    def fake_run(force):
        calls.append(force)
        return {"torproject": "ok", "danme": "skipped", "bigdatacloud": "disabled"}

    monkeypatch.setattr("app.routers.sources.run_ingestion", fake_run)
    db.add(SourceStatus(source="danme", last_status="ok", ip_count=10))
    db.commit()

    response = client.post("/sources/refresh", headers=admin)
    assert response.status_code == 200
    assert calls == [True]
    body = response.json()
    assert body["results"]["danme"] == "skipped"
    assert body["sources"][0]["source"] == "danme"


def test_refresh_conflict_when_cycle_running(client, admin, monkeypatch):
    monkeypatch.setattr("app.routers.sources.run_ingestion", lambda force: {})
    assert client.post("/sources/refresh", headers=admin).status_code == 409
