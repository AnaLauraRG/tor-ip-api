"""Clientes de las fuentes externas de IPs de Tor.

Cada fuente devuelve un conjunto de IPs ya validadas y normalizadas.
"""

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.config import Settings

BIGDATACLOUD_BATCH = 1000
BIGDATACLOUD_MAX_PAGES = 50


class SourceError(Exception):
    """Fallo al obtener una fuente. El mensaje nunca debe incluir URLs ni claves."""


@dataclass(frozen=True)
class Source:
    name: str
    interval_min: int
    enabled: bool
    fetch: Callable[[httpx.Client], set[str]]


def normalize_ip(value: str) -> str | None:
    """Devuelve la IP en su forma canónica, o None si no es una IP válida."""
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def parse_ip_lines(text: str) -> set[str]:
    """Extrae las IPs válidas de un texto con una IP por línea."""
    ips = set()
    for line in text.splitlines():
        ip = normalize_ip(line)
        if ip is not None:
            ips.add(ip)
    return ips


def _get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    try:
        response = client.get(url, **kwargs)
    except httpx.HTTPError as exc:
        # No se usa str(exc): puede contener la URL con la API key.
        raise SourceError(f"error de red ({type(exc).__name__})") from None
    if response.status_code != 200:
        raise SourceError(f"respuesta HTTP {response.status_code}")
    return response


def _fetch_text_list(url: str) -> Callable[[httpx.Client], set[str]]:
    def fetch(client: httpx.Client) -> set[str]:
        return parse_ip_lines(_get(client, url).text)

    return fetch


def _fetch_bigdatacloud(url: str, api_key: str) -> Callable[[httpx.Client], set[str]]:
    def fetch(client: httpx.Client) -> set[str]:
        ips: set[str] = set()
        offset = 0
        for _ in range(BIGDATACLOUD_MAX_PAGES):
            response = _get(
                client,
                url,
                params={"batchSize": BIGDATACLOUD_BATCH, "offset": offset, "key": api_key},
            )
            try:
                data = response.json()
                nodes = data.get("nodes") or []
                total = int(data.get("total", 0))
            except (ValueError, AttributeError, TypeError):
                raise SourceError("respuesta JSON inesperada") from None
            for node in nodes:
                ip = normalize_ip(str(node.get("ip", ""))) if isinstance(node, dict) else None
                if ip is not None:
                    ips.add(ip)
            offset += BIGDATACLOUD_BATCH
            if not nodes or offset >= total:
                break
        return ips

    return fetch


def build_sources(settings: Settings) -> list[Source]:
    return [
        Source(
            name="torproject",
            interval_min=settings.torproject_interval_min,
            enabled=True,
            fetch=_fetch_text_list(settings.torproject_url),
        ),
        Source(
            name="danme",
            interval_min=settings.danme_interval_min,
            enabled=True,
            fetch=_fetch_text_list(settings.danme_url),
        ),
        Source(
            name="bigdatacloud",
            interval_min=settings.bigdatacloud_interval_min,
            # Sin API key la fuente se omite en lugar de fallar en cada ciclo.
            enabled=bool(settings.bigdatacloud_api_key),
            fetch=_fetch_bigdatacloud(
                settings.bigdatacloud_url, settings.bigdatacloud_api_key
            ),
        ),
    ]
