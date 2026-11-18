"""Endpoints de IPs y exclusiones, con su control de acceso."""

from app.models import TorIP


def _seed(db, *pairs):
    for ip, source in pairs:
        db.add(TorIP(ip=ip, source=source))
    db.commit()


def test_list_ips_empty(client, reader):
    response = client.get("/ips", headers=reader)
    assert response.status_code == 200
    assert response.json() == {"count": 0, "ips": []}


def test_list_ips_unifies_sources(client, reader, db):
    _seed(db, ("1.1.1.1", "torproject"), ("1.1.1.1", "danme"), ("2.2.2.2", "danme"))
    body = client.get("/ips", headers=reader).json()
    assert body == {"count": 2, "ips": ["1.1.1.1", "2.2.2.2"]}


def test_add_exclusion(client, admin):
    response = client.post(
        "/exclusions", json={"ip": "1.1.1.1", "reason": "falso positivo"}, headers=admin
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ip"] == "1.1.1.1"
    assert body["reason"] == "falso positivo"
    assert body["created_at"]


def test_add_exclusion_duplicate_returns_409(client, admin):
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=admin).status_code == 201
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=admin).status_code == 409


def test_add_exclusion_invalid_ip_returns_422(client, admin):
    for bad in ["999.1.1.1", "no-es-una-ip", "1.1.1.0/24", "", "1.1.1.1; DROP TABLE x"]:
        response = client.post("/exclusions", json={"ip": bad}, headers=admin)
        assert response.status_code == 422
    assert client.post("/exclusions", json={}, headers=admin).status_code == 422


def test_filtered_excludes_registered_ips(client, admin, reader, db):
    _seed(db, ("1.1.1.1", "torproject"), ("2.2.2.2", "torproject"), ("2.2.2.2", "danme"))
    client.post("/exclusions", json={"ip": "2.2.2.2"}, headers=admin)

    assert client.get("/ips/filtered", headers=reader).json() == {
        "count": 1,
        "ips": ["1.1.1.1"],
    }
    # El listado completo no cambia.
    assert client.get("/ips", headers=reader).json()["count"] == 2


def test_ipv6_exclusion_matches_any_notation(client, admin, reader, db):
    _seed(db, ("2001:db8::1", "danme"))
    # Misma IP escrita sin abreviar: debe normalizarse y coincidir.
    response = client.post(
        "/exclusions", json={"ip": "2001:0db8:0000:0000:0000:0000:0000:0001"}, headers=admin
    )
    assert response.status_code == 201
    assert response.json()["ip"] == "2001:db8::1"
    assert client.get("/ips/filtered", headers=reader).json()["count"] == 0


def test_list_exclusions(client, admin, reader):
    assert client.get("/exclusions", headers=reader).json() == []
    client.post("/exclusions", json={"ip": "1.1.1.1", "reason": "uno"}, headers=admin)
    client.post("/exclusions", json={"ip": "2.2.2.2"}, headers=admin)
    body = client.get("/exclusions", headers=reader).json()
    assert {item["ip"] for item in body} == {"1.1.1.1", "2.2.2.2"}
    assert next(i for i in body if i["ip"] == "1.1.1.1")["reason"] == "uno"


def test_delete_exclusion(client, admin, reader, db):
    _seed(db, ("1.1.1.1", "torproject"))
    client.post("/exclusions", json={"ip": "1.1.1.1"}, headers=admin)
    assert client.get("/ips/filtered", headers=reader).json()["count"] == 0

    response = client.delete("/exclusions/1.1.1.1", headers=admin)
    assert response.status_code == 204
    assert client.get("/ips/filtered", headers=reader).json()["count"] == 1
    assert client.delete("/exclusions/1.1.1.1", headers=admin).status_code == 404


def test_delete_exclusion_normalizes_ipv6(client, admin):
    client.post("/exclusions", json={"ip": "2001:db8::1"}, headers=admin)
    response = client.delete("/exclusions/2001:0DB8:0:0:0:0:0:1", headers=admin)
    assert response.status_code == 204


def test_delete_exclusion_invalid_ip(client, admin):
    assert client.delete("/exclusions/no-es-ip", headers=admin).status_code == 422


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "sources": []}


def test_security_headers(client, reader):
    response = client.get("/ips", headers=reader)
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
