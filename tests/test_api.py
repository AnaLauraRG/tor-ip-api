from app.models import TorIP


def _seed(db, *pairs):
    for ip, source in pairs:
        db.add(TorIP(ip=ip, source=source))
    db.commit()


def test_list_ips_empty(client):
    response = client.get("/ips")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "ips": []}


def test_list_ips_unifies_sources(client, db):
    _seed(db, ("1.1.1.1", "torproject"), ("1.1.1.1", "danme"), ("2.2.2.2", "danme"))
    body = client.get("/ips").json()
    assert body == {"count": 2, "ips": ["1.1.1.1", "2.2.2.2"]}


def test_add_exclusion(client):
    response = client.post("/exclusions", json={"ip": "1.1.1.1", "reason": "falso positivo"})
    assert response.status_code == 201
    body = response.json()
    assert body["ip"] == "1.1.1.1"
    assert body["reason"] == "falso positivo"
    assert body["created_at"]


def test_add_exclusion_duplicate_returns_409(client):
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}).status_code == 201
    assert client.post("/exclusions", json={"ip": "1.1.1.1"}).status_code == 409


def test_add_exclusion_invalid_ip_returns_422(client):
    for bad in ["999.1.1.1", "no-es-una-ip", "1.1.1.0/24", "", "1.1.1.1; DROP TABLE x"]:
        assert client.post("/exclusions", json={"ip": bad}).status_code == 422
    assert client.post("/exclusions", json={}).status_code == 422


def test_filtered_excludes_registered_ips(client, db):
    _seed(db, ("1.1.1.1", "torproject"), ("2.2.2.2", "torproject"), ("2.2.2.2", "danme"))
    client.post("/exclusions", json={"ip": "2.2.2.2"})

    assert client.get("/ips/filtered").json() == {"count": 1, "ips": ["1.1.1.1"]}
    # El listado completo no cambia.
    assert client.get("/ips").json()["count"] == 2


def test_ipv6_exclusion_matches_any_notation(client, db):
    _seed(db, ("2001:db8::1", "danme"))
    # Misma IP escrita sin abreviar: debe normalizarse y coincidir.
    response = client.post(
        "/exclusions", json={"ip": "2001:0db8:0000:0000:0000:0000:0000:0001"}
    )
    assert response.status_code == 201
    assert response.json()["ip"] == "2001:db8::1"
    assert client.get("/ips/filtered").json()["count"] == 0


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "sources": []}
