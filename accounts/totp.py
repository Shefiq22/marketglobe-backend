"""Time-based one-time password (TOTP) helpers for authenticator apps.

Wraps pyotp for secret generation/verification and builds a QR-code PNG (as
base64) so the Flutter client can display the enrollment QR without any
client-side QR library.
"""

import base64
import io

import pyotp
import qrcode
from django.conf import settings


APP_NAME = getattr(settings, "TOTP_APP_NAME", "MarketGlobe")


def new_secret() -> str:
    return pyotp.random_base32()


def _totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret)


def provisioning_uri(email: str, secret: str) -> str:
    return _totp(secret).provisioning_uri(name=email, issuer_name=APP_NAME)


def verify(secret: str, code: str) -> bool:
    """Check a TOTP code against the secret. Tolerates a little clock skew."""
    try:
        return _totp(secret).verify(code, valid_window=1)
    except Exception:  # noqa: BLE001 - reject malformed codes
        return False


def qr_base64(uri: str) -> str:
    """Render a TOTP provisioning URI as a base64-encoded PNG."""
    img = qrcode.make(uri, box_size=6)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
