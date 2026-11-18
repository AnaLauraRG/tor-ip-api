from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings
from app.database import SessionLocal
from app.models import SourceStatus, TorIP, utcnow
from app.services.ingestion import run_cycle
from app.services.sources import build_sources, parse_ip_lines

API_KEY = "clave-secreta-de-prueba"


class FakeSources:
    """Simula las tres fuentes externas sin salir a internet."""

    def __init__(self):
        self.calls = {"torproject": 0, "danme": 0, "bigdatacloud": 0}
        self.torproject = "1.1.1.1\n2.2.2.2\n"
        self.danme = "2.2.2.2\n2001:db8::1\n"
        self.bigdatacloud = ["3.3.3.3"]
        self.fail = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host == "check.torproject.org":
            name, ok = "torproject", lambda: httpx.Response(200, text=self.torproject)
        elif host == "www.dan.me.uk":
            name, ok = "danme", lambda: httpx.Response(200, text=self.danme)
        else:
            name, ok = "bigdatacloud", lambda: self._bigdatacloud(request)
        self.calls[name] += 1
        return httpx.Response(403, text="bloqueado") if name in self.fail else ok()

    def _bigdatacloud(self, request):
        assert request.headers["x-bdc-key"] == API_KEY
        assert "key" not in request.url.params
        offset = int(request.url.params["offset"])
        size = int(request.url.params["batchSize"])
        nodes = [{"ip": ip} for ip in self.bigdatacloud[offset : offset + size]]
        return httpx.Response(
            200, json={"total": len(self.bigdatacloud), "offset": offset, "nodes": nodes}
        )


@pytest.fixture
def fake():
    return FakeSources()


def _run(fake, api_key=API_KEY, force=False):
    settings = Settings(_env_file=None, bigdatacloud_api_key=api_key)
    with httpx.Client(transport=httpx.MockTransport(fake.handler)) as client:
        return run_cycle(SessionLocal, build_sources(settings), client, 48, force=force)


def _age_attempts(db, minutes):
    for status in db.scalars(select(SourceStatus)).all():
        status.last_attempt_at = utcnow() - timedelta(minutes=minutes)
    db.commit()


def _ips(db):
    return set(db.scalars(select(TorIP.ip).distinct()).all())


def test_parse_ip_lines_discards_invalid():
    text = "1.1.1.1\n  2.2.2.2  \n# comentario\n999.9.9.9\n<html>\n\n2001:DB8::1\n1.1.1.1\n"
    assert parse_ip_lines(text) == {"1.1.1.1", "2.2.2.2", "2001:db8::1"}


def test_cycle_unifies_three_sources(fake, db):
    results = _run(fake)
    assert results == {"torproject": "ok", "danme": "ok", "bigdatacloud": "ok"}
    assert _ips(db) == {"1.1.1.1", "2.2.2.2", "2001:db8::1", "3.3.3.3"}
    assert db.get(SourceStatus, "danme").ip_count == 2


def test_cycle_respects_interval(fake):
    _run(fake)
    results = _run(fake)
    assert set(results.values()) == {"skipped"}
    assert fake.calls == {"torproject": 1, "danme": 1, "bigdatacloud": 1}


def test_failed_attempt_also_respects_interval(fake):
    fake.fail.add("danme")
    assert _run(fake)["danme"] == "error"
    assert _run(fake)["danme"] == "skipped"
    assert fake.calls["danme"] == 1


def test_source_due_again_after_interval(fake, db):
    _run(fake)
    status = db.get(SourceStatus, "torproject")
    status.last_attempt_at = utcnow() - timedelta(minutes=61)
    db.commit()
    fake.torproject = "1.1.1.1\n9.9.9.9\n"

    results = _run(fake)
    assert results["torproject"] == "ok"
    assert results["danme"] == "skipped"
    assert "9.9.9.9" in _ips(db)
    # 2.2.2.2 se conserva hasta que venza la ventana de 48 horas.
    assert "2.2.2.2" in _ips(db)


def test_failure_keeps_previous_data(fake, db):
    _run(fake)
    for status in db.scalars(select(SourceStatus)).all():
        status.last_attempt_at = utcnow() - timedelta(hours=2)
    db.commit()
    fake.fail.update({"torproject", "danme", "bigdatacloud"})

    results = _run(fake)
    assert set(results.values()) == {"error"}
    assert _ips(db) == {"1.1.1.1", "2.2.2.2", "2001:db8::1", "3.3.3.3"}
    db.expire_all()
    status = db.get(SourceStatus, "torproject")
    assert status.last_status == "error"
    assert status.last_error == "respuesta HTTP 403"
    assert status.last_success_at is not None


def test_empty_or_garbage_response_is_an_error(fake, db):
    fake.danme = "Umm... You can only fetch the data every 30 minutes\n"
    results = _run(fake)
    assert results["danme"] == "error"
    assert results["torproject"] == "ok"


def test_bigdatacloud_paginates(fake, db):
    fake.bigdatacloud = [f"10.0.{i // 256}.{i % 256}" for i in range(2500)]
    _run(fake)
    assert fake.calls["bigdatacloud"] == 3
    assert db.get(SourceStatus, "bigdatacloud").ip_count == 2500


def test_bigdatacloud_disabled_without_key(fake, db):
    results = _run(fake, api_key="")
    assert results["bigdatacloud"] == "disabled"
    assert fake.calls["bigdatacloud"] == 0
    assert results["torproject"] == "ok"


def test_api_key_never_stored_in_errors(db):
    def handler(request):
        raise httpx.ConnectError(f"fallo conectando a {request.url}")

    settings = Settings(_env_file=None, bigdatacloud_api_key=API_KEY)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        run_cycle(SessionLocal, build_sources(settings), client, 48)

    error = db.get(SourceStatus, "bigdatacloud").last_error
    assert error == "error de red (ConnectError)"
    assert API_KEY not in error


def test_stale_ips_are_purged(fake, db):
    db.add(TorIP(ip="8.8.8.8", source="torproject", last_seen=utcnow() - timedelta(hours=49)))
    db.add(TorIP(ip="7.7.7.7", source="torproject", last_seen=utcnow() - timedelta(hours=47)))
    db.commit()
    _run(fake)
    assert "8.8.8.8" not in _ips(db)
    assert "7.7.7.7" in _ips(db)


def test_force_skips_normal_interval_but_not_danme_minimum(fake, db):
    _run(fake)
    _age_attempts(db, 10)

    results = _run(fake, force=True)
    assert results == {"torproject": "ok", "danme": "skipped", "bigdatacloud": "ok"}
    assert fake.calls == {"torproject": 2, "danme": 1, "bigdatacloud": 2}


def test_force_downloads_danme_after_30_minutes(fake, db):
    _run(fake)
    _age_attempts(db, 31)
    assert _run(fake, force=True)["danme"] == "ok"
    assert fake.calls["danme"] == 2


def test_danme_interval_cannot_be_configured_below_30():
    with pytest.raises(ValueError):
        Settings(_env_file=None, danme_interval_min=10)
