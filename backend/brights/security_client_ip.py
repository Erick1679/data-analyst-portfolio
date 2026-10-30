"""Conservative network peer identification.

This module does not interpret reverse-proxy headers.

REMOTE_ADDR is the immediate network peer, not necessarily
the original internet client. Trusted-proxy handling must
be designed only after the hosting topology is verified.
"""

from ipaddress import ip_address


def get_network_peer_ip(request):
    """Return a validated network peer IP, or None.

    Reads only request.META["REMOTE_ADDR"].

    Never trusts client-controlled forwarding headers such as
    X-Forwarded-For, X-Real-IP, or CF-Connecting-IP.
    """
    raw = request.META.get("REMOTE_ADDR")

    if not isinstance(raw, str):
        return None

    raw = raw.strip()

    if not raw:
        return None

    try:
        return str(ip_address(raw))
    except ValueError:
        return None
