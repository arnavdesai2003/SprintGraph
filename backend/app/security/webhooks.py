"""Pure verification primitives; routes enforce configuration, payload bounds and identity."""
import hashlib
import hmac

def github_signature_valid(raw: bytes, secret: str, signature: str) -> bool:
    if not secret:
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.encode(), expected.encode())

def shared_secret_valid(secret: str, supplied: str) -> bool:
    return bool(secret) and hmac.compare_digest(secret.encode(), supplied.encode())
