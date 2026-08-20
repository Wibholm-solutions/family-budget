"""Client address resolution behind trusted reverse proxies.

The app runs behind Caddy in production, so ``request.client.host`` is the
proxy's address for every request. Rate limiting on that value collapses all
users into a single bucket. We therefore read the forwarded header, but ONLY
when the request actually arrives from a proxy we trust — an untrusted
``X-Forwarded-For`` must never let a caller rotate identities.

Configure with the ``TRUSTED_PROXY_IPS`` environment variable: a comma
separated list of IP addresses or CIDR networks. Empty means "trust nobody".
"""

import ipaddress
import logging
import os

from fastapi import Request

logger = logging.getLogger(__name__)

# Safe default: only the local loopback may present forwarded headers.
DEFAULT_TRUSTED_PROXY_IPS = "127.0.0.1,::1"

UNKNOWN_CLIENT = "unknown"


def parse_trusted_proxies(raw: str | None) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse a comma separated list of IPs/CIDRs into networks.

    Unparsable entries are ignored (and logged) rather than crashing startup.
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in (raw or "").split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            logger.warning(f"Ignoring invalid TRUSTED_PROXY_IPS entry: {candidate!r}")
    return networks


def load_trusted_proxies() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Read the trusted proxy set from the environment."""
    return parse_trusted_proxies(os.getenv("TRUSTED_PROXY_IPS", DEFAULT_TRUSTED_PROXY_IPS))


def _parse_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    candidate = value.strip()
    if not candidate:
        return None
    # Strip an IPv6 bracket/port form such as "[::1]:443" and an IPv4 "host:port".
    if candidate.startswith("["):
        candidate = candidate[1:].split("]", 1)[0]
    elif candidate.count(":") == 1:
        candidate = candidate.split(":", 1)[0]
    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_trusted(address: str, trusted_proxies) -> bool:
    parsed = _parse_address(address)
    if parsed is None:
        return False
    return any(parsed in network for network in trusted_proxies)


def get_client_ip(request: Request, trusted_proxies) -> str:
    """Return the identity to key rate limiting on.

    When the immediate peer is a trusted proxy, walk ``X-Forwarded-For`` from
    right to left and return the first address that is not itself a trusted
    proxy — that is the closest address the trusted chain actually vouches for.
    Otherwise the peer address is used and the header is ignored entirely.
    """
    peer = request.client.host if request.client else None
    if not peer:
        return UNKNOWN_CLIENT

    if not _is_trusted(peer, trusted_proxies):
        # Not behind a proxy we trust: the header is attacker-controlled.
        return peer

    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in reversed(forwarded.split(",")):
        parsed = _parse_address(hop)
        if parsed is None:
            continue
        if any(parsed in network for network in trusted_proxies):
            continue
        return str(parsed)

    # Trusted peer but no usable forwarded address — fall back to the peer.
    return peer
