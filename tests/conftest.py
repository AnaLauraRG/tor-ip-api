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

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
