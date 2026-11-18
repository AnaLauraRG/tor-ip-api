import os
import tempfile

# La configuración se fija antes de importar la aplicación.
# Por defecto las pruebas usan SQLite; con TEST_DATABASE_URL se pueden correr
# contra un PostgreSQL de pruebas (se borran y recrean las tablas en cada test).
_db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite:///{_db_file}"
)
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["BIGDATACLOUD_API_KEY"] = ""
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-mas-de-32-caracteres"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-password-123"
# Costo mínimo de bcrypt para que las pruebas sean rápidas.
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["LOGIN_MAX_ATTEMPTS"] = "3"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.security import hash_password, login_limiter  # noqa: E402

ADMIN = ("admin", "admin-password-123")
READER = ("lector", "lector-password-123")


@pytest.fixture(autouse=True)
def clean_state():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    login_limiter.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    # Al entrar, el lifespan de la aplicación crea el administrador inicial.
    with TestClient(app) as test_client:
        with SessionLocal() as session:
            session.add(
                User(
                    username=READER[0],
                    password_hash=hash_password(READER[1]),
                    role=Role.READER.value,
                )
            )
            session.commit()
        yield test_client


def login(client, username, password):
    return client.post("/auth/login", data={"username": username, "password": password})


def auth_headers(client, credentials):
    response = login(client, *credentials)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return auth_headers(client, ADMIN)


@pytest.fixture
def reader(client):
    return auth_headers(client, READER)
