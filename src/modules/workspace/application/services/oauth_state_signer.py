# -*- coding: utf-8 -*-
"""OAuth state signer service.

Creates and verifies HMAC-signed OAuth state tokens
for stateless CSRF protection. No FastAPI or HTTP dependencies.
"""

import hashlib
import hmac
import secrets
import time


class InvalidOAuthStateError(Exception):
    """Raised when OAuth state verification fails."""
    pass


class OAuthStateSigner:
    """HMAC-based OAuth state token signer/verifier."""

    def __init__(self, secret: str, ttl_seconds: int = 600):
        self._key = secret.encode()
        self._ttl = ttl_seconds

    def create(self) -> str:
        """Create a signed OAuth state token.

        Format: {nonce}.{timestamp}.{signature}
        """
        nonce = secrets.token_hex(16)
        timestamp = str(int(time.time()))
        message = f"{nonce}.{timestamp}".encode()
        signature = hmac.new(self._key, message, hashlib.sha256).hexdigest()
        return f"{nonce}.{timestamp}.{signature}"

    def verify(self, state: str) -> bool:
        """Verify a signed OAuth state token.

        Checks HMAC signature integrity and TTL expiry.
        """
        parts = state.split(".")
        if len(parts) != 3:
            return False

        nonce, timestamp, signature = parts

        try:
            ts = int(timestamp)
        except ValueError:
            return False

        if time.time() - ts > self._ttl:
            return False

        message = f"{nonce}.{timestamp}".encode()
        expected = hmac.new(self._key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
